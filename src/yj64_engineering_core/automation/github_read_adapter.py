"""Read-only GitHub executor adapter for universal parent tasks.

The adapter exposes a small, explicit GET-only surface. It never creates
branches, commits, pull requests, workflow runs, releases, or repository files.
Repository content and GitHub metadata are untrusted input.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping

from .checkpoints import create_checkpoint
from .parent_tasks import ParentTaskState, TaskAdapterRegistry
from .worker import TaskExecutionResult

_GITHUB_API = "https://api.github.com"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[a-f0-9]{40}$")
_MAX_RESPONSE_BYTES = 256 * 1024
_MAX_FILE_BYTES = 128 * 1024
_ALLOWED_OPERATIONS = {
    "repository.get", "commit.get", "workflow_run.get",
    "workflow_runs.list", "file.get",
}


class GitHubReadError(RuntimeError):
    """Safe classification for a failed read-only GitHub API request."""

    def __init__(self, reason: str, *, retryable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


class GitHubReadOnlyClient:
    """Minimal GitHub REST client whose only HTTP method is GET."""

    def __init__(
        self,
        token: str,
        *,
        opener: Callable | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("GitHub read token is required")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be between 1 and 60")
        self._token = token.strip()
        self._opener = opener or urllib.request.urlopen
        self._timeout = float(timeout_seconds)

    def get_json(self, endpoint: str) -> dict:
        if (
            not isinstance(endpoint, str)
            or not endpoint.startswith("/repos/")
            or endpoint.startswith("//")
            or ".." in endpoint.split("/")
            or "#" in endpoint
            or len(endpoint) > 2048
        ):
            raise ValueError("GitHub endpoint is outside the read-only repository API")
        request = urllib.request.Request(
            _GITHUB_API + endpoint,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self._token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "YJ64-Engineering-Core",
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise GitHubReadError(
                        "github_http_" + str(status),
                        retryable=status in {408, 429} or status >= 500,
                    )
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raise GitHubReadError(
                "github_http_" + str(status),
                retryable=status in {408, 429} or status >= 500,
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GitHubReadError("github_transport_error", retryable=True) from None
        if not isinstance(raw, bytes) or len(raw) > _MAX_RESPONSE_BYTES:
            raise GitHubReadError("github_response_too_large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubReadError("github_response_invalid_json") from None
        if not isinstance(payload, dict):
            raise GitHubReadError("github_response_shape_invalid")
        return payload


class GitHubReadTaskAdapter:
    """Execute one allowlisted GitHub GET operation and checkpoint its evidence."""

    def __init__(
        self,
        client: Any,
        *,
        allowed_repositories: tuple[str, ...] | list[str],
    ) -> None:
        if not callable(getattr(client, "get_json", None)):
            raise TypeError("client must implement get_json(endpoint)")
        if not isinstance(allowed_repositories, (tuple, list)) or not allowed_repositories:
            raise ValueError("allowed_repositories must be a non-empty list")
        repos = tuple(allowed_repositories)
        if any(not isinstance(repo, str) or not _REPOSITORY.fullmatch(repo) for repo in repos):
            raise ValueError("allowed_repositories contains an invalid repository")
        if len(set(repos)) != len(repos):
            raise ValueError("allowed_repositories must be unique")
        self.client = client
        self.allowed_repositories = frozenset(repos)

    def __call__(
        self,
        request: Any,
        state: ParentTaskState,
        context: Any,
    ) -> TaskExecutionResult:
        if state.stage == "council_result_received":
            return TaskExecutionResult("blocked", "github_adapter_cannot_consume_council_result")
        try:
            data = request.input_data
            operation = data.get("operation")
            repository = data.get("repository")
            if operation not in _ALLOWED_OPERATIONS:
                return TaskExecutionResult("blocked", "github_read_operation_not_allowed")
            if repository not in self.allowed_repositories:
                return TaskExecutionResult("blocked", "github_repository_not_allowed")
            base = "/repos/" + repository
            if operation == "repository.get":
                result = self.client.get_json(base)
                evidence = _repository_summary(result)
            elif operation == "commit.get":
                sha = data.get("commit_sha")
                if not isinstance(sha, str) or not _SHA.fullmatch(sha):
                    return TaskExecutionResult("blocked", "github_commit_sha_invalid")
                result = self.client.get_json(base + "/commits/" + sha)
                commit = result.get("commit") if isinstance(result.get("commit"), dict) else {}
                evidence = {
                    "sha": result.get("sha"),
                    "message": commit.get("message"),
                    "html_url": result.get("html_url"),
                }
            elif operation == "workflow_run.get":
                run_id = data.get("run_id")
                if not _positive_int(run_id):
                    return TaskExecutionResult("blocked", "github_run_id_invalid")
                result = self.client.get_json(base + "/actions/runs/" + str(run_id))
                evidence = _workflow_run_summary(result)
            elif operation == "workflow_runs.list":
                per_page = data.get("per_page", 10)
                if not isinstance(per_page, int) or isinstance(per_page, bool) or not 1 <= per_page <= 20:
                    return TaskExecutionResult("blocked", "github_per_page_invalid")
                params = {"per_page": per_page}
                branch = data.get("branch")
                if branch is not None:
                    if not _safe_ref(branch):
                        return TaskExecutionResult("blocked", "github_branch_invalid")
                    params["branch"] = branch
                endpoint = base + "/actions/runs?" + urllib.parse.urlencode(params)
                result = self.client.get_json(endpoint)
                runs = result.get("workflow_runs")
                if not isinstance(runs, list):
                    raise GitHubReadError("github_workflow_runs_shape_invalid")
                evidence = {
                    "total_count": result.get("total_count"),
                    "workflow_runs": [
                        _workflow_run_summary(item) for item in runs[:per_page]
                        if isinstance(item, dict)
                    ],
                }
            else:  # file.get
                path = data.get("path")
                ref = data.get("ref", "main")
                if not _safe_repo_path(path):
                    return TaskExecutionResult("blocked", "github_file_path_invalid")
                if not _safe_ref(ref):
                    return TaskExecutionResult("blocked", "github_file_ref_invalid")
                endpoint = base + "/contents/" + "/".join(
                    urllib.parse.quote(part, safe="") for part in path.split("/")
                ) + "?" + urllib.parse.urlencode({"ref": ref})
                result = self.client.get_json(endpoint)
                if result.get("encoding") != "base64" or not isinstance(result.get("content"), str):
                    raise GitHubReadError("github_file_encoding_unsupported")
                try:
                    raw = base64.b64decode(result["content"], validate=False)
                except (ValueError, TypeError):
                    raise GitHubReadError("github_file_content_invalid") from None
                if len(raw) > _MAX_FILE_BYTES:
                    raise GitHubReadError("github_file_too_large")
                try:
                    file_text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    raise GitHubReadError("github_file_not_utf8") from None
                evidence = {
                    "path": path,
                    "ref": ref,
                    "blob_sha": result.get("sha"),
                    "content": file_text,
                    "content_trust": "untrusted_repository_data",
                }

            previous = context.load_latest_checkpoint()
            sequence = int(previous.get("sequence", 0)) + 1 if isinstance(previous, dict) else 1
            previous_hash = previous.get("checkpoint_hash") if isinstance(previous, dict) else None
            checkpoint = create_checkpoint(
                task_id=str(context.task_id),
                sequence=sequence,
                state="completed",
                task_spec_version=request.contract_version,
                task_state={
                    "stage": "github_read_completed",
                    "task_type": request.task_type,
                    "operation": operation,
                    "repository": repository,
                    "github_evidence": evidence,
                    "evidence_is_untrusted": True,
                    "resume_state": dict(state.resume_state),
                },
                budgets=dict(request.constraints),
                approvals=dict(request.approval_policy),
                artifact_refs=list(state.artifact_refs),
                previous_checkpoint_hash=previous_hash,
            )
            if not context.save_checkpoint(checkpoint):
                return TaskExecutionResult("retry", "github_result_checkpoint_failed", 90)
            return TaskExecutionResult("completed")
        except GitHubReadError as exc:
            return TaskExecutionResult(
                "retry" if exc.retryable else "blocked",
                exc.reason,
                90,
            )
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "invalid_github_read_task_input")


def register_github_read_adapter(
    registry: TaskAdapterRegistry,
    client: Any,
    *,
    allowed_repositories: tuple[str, ...] | list[str],
) -> None:
    """Register the read-only GitHub executor explicitly; no auto-discovery."""
    if not isinstance(registry, TaskAdapterRegistry):
        raise TypeError("registry must be a TaskAdapterRegistry")
    registry.register(
        "github.read",
        GitHubReadTaskAdapter(client, allowed_repositories=allowed_repositories),
        capabilities=("github.read",),
        council_enabled=False,
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _safe_ref(value: Any) -> bool:
    return (
        isinstance(value, str) and 1 <= len(value) <= 255
        and not value.startswith("-") and ".." not in value
        and not value.startswith("/") and not value.endswith("/")
        and "\\" not in value and not any(ord(char) < 32 for char in value)
    )


def _safe_repo_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 512 or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts) and not value.startswith("/")


def _repository_summary(data: Mapping[str, Any]) -> dict:
    return {
        key: data.get(key)
        for key in ("full_name", "default_branch", "private", "archived", "html_url", "visibility")
        if key in data
    }


def _workflow_run_summary(data: Mapping[str, Any]) -> dict:
    return {
        key: data.get(key)
        for key in (
            "id", "name", "event", "status", "conclusion", "head_sha",
            "head_branch", "html_url", "created_at", "updated_at",
        )
        if key in data
    }
