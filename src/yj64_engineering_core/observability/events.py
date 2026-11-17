"""Versioned, vendor-neutral diagnostic event contract and redaction.

This module is intentionally dependency-free. It defines the portable event
boundary; exporters, persistence, metrics and tracing are separate adapters.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

EVENT_SCHEMA = "yj64.diagnostic.v1"
_ALLOWED_SEVERITIES = {"debug", "info", "warning", "error", "critical"}
_ALLOWED_OUTCOMES = {"started", "succeeded", "failed", "blocked", "degraded"}
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
_SENSITIVE_KEY = re.compile(
    r"(?:secret|password|passwd|token|api[_-]?key|authorization|cookie|"
    r"credential|private[_-]?key|database[_-]?url|connection[_-]?string|"
    r"access[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIALS = re.compile(r"(://)[^/@\s]+:[^/@\s]+@")


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a non-empty stable identifier")


def _redact_string(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    return _URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)


def redact_sensitive_data(value: Any, *, _key: str = "") -> Any:
    """Return a JSON-safe copy with sensitive-key values and common secrets masked."""
    if _key and _SENSITIVE_KEY.search(_key):
        return "[REDACTED]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("diagnostic context keys must be strings")
            result[key] = redact_sensitive_data(item, _key=key)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"diagnostic context contains unsupported type {type(value).__name__}")


@dataclass(frozen=True)
class DiagnosticEvent:
    """A single correlated, structured event emitted by any YJ64 component."""

    event_id: str
    event_name: str
    severity: str
    outcome: str
    service: str
    component: str
    environment: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    module: str | None = None
    discipline: str | None = None
    agent: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    correlation_id: str | None = None
    task_id: str | None = None
    parent_task_id: str | None = None
    repository: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    workflow_run_id: str | None = None
    job_id: str | None = None
    deployment_version: str | None = None
    operation: str | None = None
    duration_ms: float | None = None
    attempt: int | None = None
    error_code: str | None = None
    exception_type: str | None = None
    http_status: int | None = None
    sqlstate: str | None = None
    exit_code: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    schema: str = EVENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVENT_SCHEMA:
            raise ValueError(f"Unsupported diagnostic schema: {self.schema}")
        for name in ("event_id", "event_name", "service", "component", "environment"):
            _require_id(getattr(self, name), name)
        if self.severity not in _ALLOWED_SEVERITIES:
            raise ValueError("unsupported diagnostic severity")
        if self.outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported diagnostic outcome")
        for name in (
            "module", "discipline", "agent", "trace_id", "span_id", "correlation_id",
            "task_id", "parent_task_id", "repository", "branch", "commit_sha",
            "workflow_run_id", "job_id", "deployment_version", "operation", "error_code",
            "exception_type",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_id(value, name)
        try:
            parsed = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("timestamp must be an ISO-8601 datetime") from exc
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        if self.duration_ms is not None and (isinstance(self.duration_ms, bool) or self.duration_ms < 0):
            raise ValueError("duration_ms must be non-negative")
        if self.attempt is not None and (isinstance(self.attempt, bool) or self.attempt < 1):
            raise ValueError("attempt must be a positive integer")
        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("http_status must be between 100 and 599")
        if self.sqlstate is not None and not re.fullmatch(r"[0-9A-Z]{5}", self.sqlstate):
            raise ValueError("sqlstate must be a five-character SQLSTATE code")
        if not isinstance(self.attributes, dict):
            raise TypeError("attributes must be an object")
        # Validate and redact eagerly so unsafe values cannot be serialized later.
        object.__setattr__(self, "attributes", redact_sensitive_data(self.attributes))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)
