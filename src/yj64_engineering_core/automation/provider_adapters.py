"""Provider adapter contracts for safe durable request/response orchestration.

This module intentionally contains no HTTP client and no credential handling.
Concrete adapters must persist successful response bodies as artifacts before
returning a completed result; only opaque artifact references cross this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, runtime_checkable

from .provider_budget import ProviderLimitProfile


@dataclass(frozen=True)
class ProviderCapabilities:
    idempotency_keys: bool = False
    lookup_by_request_id: bool = False
    lookup_by_idempotency_key: bool = False
    streaming: bool = False
    remote_file_ingestion: bool = False
    stateful_conversations: bool = False
    detailed_usage: bool = False

    def __post_init__(self):
        for name in (
            "idempotency_keys", "lookup_by_request_id",
            "lookup_by_idempotency_key", "streaming",
            "remote_file_ingestion", "stateful_conversations",
            "detailed_usage",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")


@dataclass(frozen=True)
class ProviderRequest:
    provider: str
    model: str
    endpoint: str
    idempotency_key: str
    payload: bytes
    payload_sha256: str
    input_tokens: int
    max_output_tokens: int

    def __post_init__(self):
        for name in ("provider", "model", "endpoint", "idempotency_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ValueError("payload must be non-empty serialized request bytes")
        actual_hash = sha256(self.payload).hexdigest()
        if self.payload_sha256 != actual_hash:
            raise ValueError("payload_sha256 does not match exact serialized request bytes")
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("max_output_tokens", self.max_output_tokens),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def payload_bytes(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class ProviderSendResult:
    outcome: str
    provider_request_id: str | None = None
    response_artifact_ref: str | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_cost_usd: str | None = None
    http_status: int | None = None
    error_classification: str | None = None
    retry_after_seconds: float | None = None
    quota_reset_at: str | None = None

    def __post_init__(self):
        if self.outcome not in {"completed", "failed", "unknown"}:
            raise ValueError("outcome must be completed, failed or unknown")
        if self.outcome == "completed" and not self.response_artifact_ref:
            raise ValueError("completed responses must be durably persisted before returning")
        if self.response_artifact_ref is not None and (
            "?" in self.response_artifact_ref or "#" in self.response_artifact_ref
        ):
            raise ValueError("response_artifact_ref must be an opaque artifact reference")
        for name, value in (
            ("actual_input_tokens", self.actual_input_tokens),
            ("actual_output_tokens", self.actual_output_tokens),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")


@dataclass(frozen=True)
class ProviderLookupResult:
    status: str
    evidence_ref: str | None = None
    provider_request_id: str | None = None
    response_artifact_ref: str | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_cost_usd: str | None = None

    def __post_init__(self):
        if self.status not in {"found", "not_found", "unknown"}:
            raise ValueError("status must be found, not_found or unknown")
        if self.status in {"found", "not_found"} and not self.evidence_ref:
            raise ValueError("authoritative lookup outcomes require an evidence reference")
        if self.status == "found" and not self.response_artifact_ref:
            raise ValueError("found responses require a durable response artifact")
        for value in (self.evidence_ref, self.response_artifact_ref):
            if value is not None and ("?" in value or "#" in value):
                raise ValueError("lookup references must be opaque, not signed URLs")


@runtime_checkable
class ProviderAdapter(Protocol):
    """Concrete adapters own auth, transport, provider-specific limits and storage."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        ...

    def get_limit_profile(self) -> ProviderLimitProfile:
        """Return an account/model/endpoint profile with an explicit freshness policy."""
        ...

    def count_tokens(self, payload: bytes) -> int:
        """Count the exact serialized request using the provider/model tokenizer."""
        ...

    def send_and_persist(self, request: ProviderRequest) -> ProviderSendResult:
        """Send with the stable idempotency key when supported and persist the full response."""
        ...

    def lookup(
        self, *, provider_request_id: str | None,
        idempotency_key: str, payload_sha256: str,
    ) -> ProviderLookupResult:
        """Return authoritative delivery status or unknown; never guess non-delivery."""
        ...
