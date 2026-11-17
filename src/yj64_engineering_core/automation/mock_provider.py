"""Deterministic, offline provider adapter and artifact store for integration tests.

This module is a test double only. It performs no network calls, reads no
credentials, and must never be selected for production model execution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Protocol, runtime_checkable

from .provider_adapters import (
    ProviderCapabilities,
    ProviderLookupResult,
    ProviderRequest,
    ProviderSendResult,
)
from .provider_budget import ProviderLimitProfile


@runtime_checkable
class ArtifactStore(Protocol):
    """Minimal durable-artifact boundary used by provider adapters."""

    def put(self, *, namespace: str, content: bytes, content_type: str) -> str:
        """Persist bytes and return an opaque, non-URL artifact reference."""

    def get(self, artifact_ref: str) -> bytes:
        """Retrieve the exact bytes addressed by an artifact reference."""


@dataclass(frozen=True)
class StoredArtifact:
    artifact_ref: str
    sha256: str
    size_bytes: int
    content_type: str


class InMemoryArtifactStore:
    """Process-local artifact store for tests; data is lost when the process exits."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self._metadata: dict[str, StoredArtifact] = {}

    def put(self, *, namespace: str, content: bytes, content_type: str) -> str:
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("namespace is required")
        if not isinstance(content, bytes):
            raise ValueError("content must be bytes")
        if not isinstance(content_type, str) or not content_type.strip():
            raise ValueError("content_type is required")
        digest = sha256(content).hexdigest()
        artifact_ref = f"memory-artifact://{namespace.strip('/')}/{digest}"
        existing = self._objects.get(artifact_ref)
        if existing is not None and existing != content:
            raise RuntimeError("artifact hash collision")
        self._objects[artifact_ref] = content
        self._metadata[artifact_ref] = StoredArtifact(
            artifact_ref=artifact_ref,
            sha256=digest,
            size_bytes=len(content),
            content_type=content_type,
        )
        return artifact_ref

    def get(self, artifact_ref: str) -> bytes:
        try:
            return self._objects[artifact_ref]
        except KeyError as exc:
            raise KeyError("artifact does not exist in this in-memory store") from exc

    def metadata(self, artifact_ref: str) -> StoredArtifact:
        try:
            return self._metadata[artifact_ref]
        except KeyError as exc:
            raise KeyError("artifact metadata does not exist") from exc


class MockProviderAdapter:
    """Offline ProviderAdapter implementation for deterministic integration tests.

    The default responder returns a JSON acknowledgement. A custom responder
    may be injected by tests, but receives only the exact request bytes.
    """

    def __init__(
        self,
        *,
        profile: ProviderLimitProfile,
        artifact_store: ArtifactStore,
        responder: Callable[[bytes], bytes] | None = None,
    ) -> None:
        if not isinstance(profile, ProviderLimitProfile):
            raise ValueError("profile must be a ProviderLimitProfile")
        if not isinstance(artifact_store, ArtifactStore):
            raise ValueError("artifact_store must implement ArtifactStore")
        self._profile = profile
        self._artifacts = artifact_store
        self._responder = responder or self._default_responder
        self._sent: dict[str, tuple[str, str, int, int]] = {}

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            idempotency_keys=True,
            lookup_by_request_id=True,
            lookup_by_idempotency_key=True,
            streaming=False,
            remote_file_ingestion=False,
            stateful_conversations=False,
            detailed_usage=True,
        )

    def get_limit_profile(self) -> ProviderLimitProfile:
        return self._profile

    def count_tokens(self, payload: bytes) -> int:
        if not isinstance(payload, bytes):
            raise ValueError("payload must be bytes")
        # Deliberately approximate: this is NOT a provider tokenizer.
        return max(1, (len(payload) + 3) // 4)

    def send_and_persist(self, request: ProviderRequest) -> ProviderSendResult:
        self._validate_request(request)
        prior = self._sent.get(request.idempotency_key)
        if prior is not None:
            prior_hash, artifact_ref, input_tokens, output_tokens = prior
            if prior_hash != request.payload_sha256:
                raise ValueError("idempotency key reused with different payload")
            return ProviderSendResult(
                outcome="completed",
                provider_request_id=f"mock-{request.idempotency_key}",
                response_artifact_ref=artifact_ref,
                actual_input_tokens=input_tokens,
                actual_output_tokens=output_tokens,
                http_status=200,
            )

        response = self._responder(request.payload)
        if not isinstance(response, bytes) or not response:
            raise ValueError("mock responder must return non-empty bytes")
        artifact_ref = self._artifacts.put(
            namespace="mock-provider-responses",
            content=response,
            content_type="application/json",
        )
        output_tokens = self.count_tokens(response)
        self._sent[request.idempotency_key] = (
            request.payload_sha256, artifact_ref, request.input_tokens, output_tokens,
        )
        return ProviderSendResult(
            outcome="completed",
            provider_request_id=f"mock-{request.idempotency_key}",
            response_artifact_ref=artifact_ref,
            actual_input_tokens=request.input_tokens,
            actual_output_tokens=output_tokens,
            http_status=200,
        )

    def lookup(
        self, *, provider_request_id: str | None,
        idempotency_key: str, payload_sha256: str,
    ) -> ProviderLookupResult:
        prior = self._sent.get(idempotency_key)
        if prior is None:
            return ProviderLookupResult(
                status="not_found",
                evidence_ref=f"mock-lookup:{idempotency_key}:absent",
                provider_request_id=provider_request_id,
            )
        prior_hash, artifact_ref, input_tokens, output_tokens = prior
        if prior_hash != payload_sha256:
            return ProviderLookupResult(status="unknown")
        return ProviderLookupResult(
            status="found",
            evidence_ref=f"mock-lookup:{idempotency_key}:found",
            provider_request_id=provider_request_id or f"mock-{idempotency_key}",
            response_artifact_ref=artifact_ref,
            actual_input_tokens=input_tokens,
            actual_output_tokens=output_tokens,
        )

    def _validate_request(self, request: ProviderRequest) -> None:
        if not isinstance(request, ProviderRequest):
            raise ValueError("request must be a ProviderRequest")
        expected = (self._profile.provider, self._profile.model, self._profile.endpoint)
        actual = (request.provider, request.model, request.endpoint)
        if actual != expected:
            raise ValueError("request provider/model/endpoint does not match mock profile")

    @staticmethod
    def _default_responder(payload: bytes) -> bytes:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {"request_sha256": sha256(payload).hexdigest()}
        response = {
            "mock": True,
            "accepted": True,
            "input": decoded,
        }
        return json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
