"""Bounded, read-only retrieval and sanitization of GitHub Actions run logs."""
from __future__ import annotations

import io
import os
import re
import urllib.error
import urllib.request
import zipfile
from typing import Callable

EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
ANDROID_RUNTIME_REPOSITORY = "concreteballs/yj64-clean-bial2modFun5"
ALLOWED_REPOSITORIES = frozenset({EXPECTED_REPOSITORY, ANDROID_RUNTIME_REPOSITORY})
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_LOG_FILES = 100
MAX_SINGLE_LOG_BYTES = 2 * 1024 * 1024


class GitHubLogsError(RuntimeError):
    def __init__(self, classification: str, *, retryable: bool) -> None:
        super().__init__(classification)
        self.classification = classification
        self.retryable = retryable


def redact_log_text(text: str, secrets: tuple[str, ...] | list[str] = ()) -> str:
    """Remove known credentials and common token formats before durable storage."""
    for secret in sorted(
        (item for item in secrets if isinstance(item, str) and len(item) >= 6),
        key=len,
        reverse=True,
    ):
        text = text.replace(secret, "[REDACTED]")
    patterns = (
        (r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+", r"\1[REDACTED]"),
        (r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", "[REDACTED_GITHUB_TOKEN]"),
        (r"\bAIza[0-9A-Za-z_-]{25,}\b", "[REDACTED_GOOGLE_KEY]"),
        (r"\bsk-[A-Za-z0-9_-]{20,}\b", "[REDACTED_API_KEY]"),
        (r"(?i)\b(postgres(?:ql)?://)[^:/\s]+:[^@/\s]+@", r"\1[REDACTED]@"),
        (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "[REDACTED_JWT]"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def extract_text_logs(
    archive_bytes: bytes,
    *,
    secrets: tuple[str, ...] | list[str] = (),
    max_log_bytes: int = MAX_LOG_BYTES,
) -> str:
    """Read only bounded .txt members; never extract archive paths to disk."""
    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise GitHubLogsError("empty_log_archive", retryable=True)
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise GitHubLogsError("log_archive_too_large", retryable=False)
    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError):
        raise GitHubLogsError("invalid_log_archive", retryable=True) from None

    sections: list[str] = []
    total = 0
    files_seen = 0
    with archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            name = info.filename
            if info.is_dir() or not name.lower().endswith(".txt"):
                continue
            normalized = name.replace("\\", "/")
            if normalized.startswith("/") or any(part in {".", ".."} for part in normalized.split("/")):
                raise GitHubLogsError("unsafe_log_archive_path", retryable=False)
            files_seen += 1
            if files_seen > MAX_LOG_FILES or info.file_size > MAX_SINGLE_LOG_BYTES:
                raise GitHubLogsError("log_archive_entry_limit", retryable=False)
            total += info.file_size
            if total > max_log_bytes:
                raise GitHubLogsError("run_logs_exceed_storage_limit", retryable=False)
            try:
                raw = archive.read(info)
            except (KeyError, RuntimeError, OSError, zipfile.BadZipFile):
                raise GitHubLogsError("corrupt_log_archive_entry", retryable=True) from None
            if len(raw) != info.file_size:
                raise GitHubLogsError("truncated_log_archive_entry", retryable=True)
            decoded = raw.decode("utf-8", errors="replace")
            decoded = redact_log_text(decoded, secrets)
            sections.append(f"===== {name} =====\n{decoded.rstrip()}\n")

    if not sections:
        raise GitHubLogsError("no_text_logs_in_archive", retryable=True)
    result = "\n".join(sections)
    if len(result.encode("utf-8")) > max_log_bytes:
        raise GitHubLogsError("run_logs_exceed_storage_limit", retryable=False)
    return result


def fetch_run_logs(
    repository: str,
    run_id: int,
    run_attempt: int,
    token: str,
    *,
    opener: Callable | None = None,
    timeout_seconds: float = 30.0,
) -> bytes:
    """Download the ZIP for one exact workflow-run attempt using a read-only token."""
    if repository not in ALLOWED_REPOSITORIES:
        raise ValueError("repository is outside the configured YJ64 scope")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError("run_id must be a positive integer")
    if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1:
        raise ValueError("run_attempt must be a positive integer")
    if repository == EXPECTED_REPOSITORY and (not isinstance(token, str) or not token.strip()):
        raise ValueError("github_token is required for the Engineering Core repository")

    url = (
        f"https://api.github.com/repos/{repository}/actions/runs/"
        f"{run_id}/attempts/{run_attempt}/logs"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YJ64-Engineering-Core",
    }
    # Never forward the Core token to the separate public Android repository.
    request_token = token.strip() if repository == EXPECTED_REPOSITORY else os.environ.get(
        "YJ64_ANDROID_REPO_LOGS_TOKEN", ""
    ).strip()
    if request_token:
        headers["Authorization"] = "Bearer " + request_token
    request = urllib.request.Request(url, headers=headers, method="GET")
    send = opener or urllib.request.urlopen
    try:
        with send(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise GitHubLogsError(
                    "github_logs_http_" + str(status),
                    retryable=status in {404, 408, 410, 429} or status >= 500,
                )
            body = response.read(MAX_ARCHIVE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raise GitHubLogsError(
            "github_logs_http_" + str(status),
            retryable=status in {404, 408, 410, 429} or status >= 500,
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GitHubLogsError("github_logs_transport_error", retryable=True) from None

    if not isinstance(body, bytes) or not body:
        raise GitHubLogsError("empty_log_archive", retryable=True)
    if len(body) > MAX_ARCHIVE_BYTES:
        raise GitHubLogsError("log_archive_too_large", retryable=False)
    return body
