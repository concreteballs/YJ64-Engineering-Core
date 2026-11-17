"""Gemini Developer API adapter for durable, budget-gated text analysis.

The adapter never retries a generation request internally. A transport failure
after dispatch is UNKNOWN because Gemini generateContent has no lookup-by-key
or idempotency guarantee. The orchestrator must retain that ambiguity.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Callable, Protocol

from .provider_adapters import (
    ProviderCapabilities,
    ProviderLookupResult,
    ProviderRequest,
    ProviderSendResult,
)
from .provider_budget import ProviderLimitProfile
from .provider_limits import classify_provider_error


class ArtifactWriter(Protocol):
    def put(self, *, namespace: str, content: bytes, content_type: str) -> str: ...


class GeminiApiError(RuntimeError):
    """Safe, classified failure from the token-counting endpoint."""

    def __init__(self, classification: str, status_code: int | None = None) -> None:
        super().__init__(classification)
        self.classification = classification
        self.status_code = status_code


class GeminiGenerateContentAdapter:
    provider = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        *,
        model: str,
        limit_profile: ProviderLimitProfile,
        artifact_store: ArtifactWriter,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        max_response_bytes: int = 4 * 1024 * 1024,
        opener: Callable | None = None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model is required")
        if not isinstance(limit_profile, ProviderLimitProfile):
            raise ValueError("an explicit verified provider limit profile is required")
        if (
            limit_profile.provider != self.provider
            or limit_profile.model != model
            or limit_profile.endpoint != "generateContent"
        ):
            raise ValueError("limit profile does not match the configured Gemini model/endpoint")
        if not callable(getattr(artifact_store, "put", None)):
            raise ValueError("artifact_store must provide put()")
        key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("GEMINI_API_KEY is required")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool) or max_response_bytes < 1024:
            raise ValueError("max_response_bytes must be at least 1024")

        if (
            limit_profile.input_cost_per_million_usd is None
            or limit_profile.output_cost_per_million_usd is None
            or limit_profile.max_input_tokens is None
            or limit_profile.max_output_tokens is None
            or limit_profile.max_payload_bytes is None
            or limit_profile.max_concurrency is None
        ):
            raise ValueError("Gemini profile must include verified token/byte/concurrency limits and pricing")
        self.model = model.strip()
        self.profile = limit_profile
        self._artifacts = artifact_store
        self._api_key = key.strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self._opener = opener or urllib.request.urlopen

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            idempotency_keys=False,
            lookup_by_request_id=False,
            lookup_by_idempotency_key=False,
            streaming=False,
            remote_file_ingestion=False,
            stateful_conversations=False,
            detailed_usage=True,
        )

    def get_limit_profile(self) -> ProviderLimitProfile:
        return self.profile

    def count_tokens(self, payload: bytes) -> int:
        """Use Gemini countTokens for model-specific input counting; no generation occurs."""
        body = self._decode_request(payload)
        count_request = dict(body)
        declared_model = count_request.pop("model", None)
        if declared_model not in (None, self.model, "models/" + self.model):
            raise ValueError("request body model does not match adapter model")
        count_request["model"] = "models/" + self.model
        count_body = json.dumps(
            {"generateContentRequest": count_request},
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        response_body, status, headers = self._post(
            self._model_url("countTokens"), count_body
        )
        if status < 200 or status >= 300:
            decision = classify_provider_error(status, self._error_message(response_body), headers)
            raise GeminiApiError(decision.classification, status)
        try:
            response = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GeminiApiError("invalid_count_tokens_response", status) from None
        total = response.get("totalTokens") if isinstance(response, dict) else None
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise GeminiApiError("invalid_count_tokens_response", status)
        return total

    def send_and_persist(self, request: ProviderRequest) -> ProviderSendResult:
        """Send one generation request and persist the full response before success."""
        if not isinstance(request, ProviderRequest):
            raise ValueError("request must be a ProviderRequest")
        if (
            request.provider != self.provider
            or request.model != self.model
            or request.endpoint != "generateContent"
        ):
            raise ValueError("request provider/model/endpoint does not match this adapter")
        body = self._decode_request(request.payload)
        generation_config = body.get("generationConfig")
        configured_output = (
            generation_config.get("maxOutputTokens")
            if isinstance(generation_config, dict) else None
        )
        if configured_output != request.max_output_tokens:
            raise ValueError("request max_output_tokens must match generationConfig.maxOutputTokens")
        try:
            response_body, status, headers = self._post(
                self._model_url("generateContent"), request.payload
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            # Once dispatch begins, transport failure is ambiguous; never blindly resend.
            return ProviderSendResult(
                outcome="unknown",
                error_classification="ambiguous_transport_outcome",
            )

        if status < 200 or status >= 300:
            decision = classify_provider_error(
                status, self._error_message(response_body), headers
            )
            return ProviderSendResult(
                outcome="failed",
                http_status=status,
                error_classification=decision.classification,
                retry_after_seconds=float(decision.delay_seconds) if decision.delay_seconds is not None else None,
            )

        try:
            parsed = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ProviderSendResult(
                outcome="unknown",
                http_status=status,
                error_classification="invalid_success_response",
            )
        if not isinstance(parsed, dict) or not isinstance(parsed.get("candidates"), list):
            return ProviderSendResult(
                outcome="unknown",
                http_status=status,
                error_classification="incomplete_success_response",
            )

        usage = parsed.get("usageMetadata")
        if not isinstance(usage, dict):
            usage = {}
        input_tokens = self._nonnegative_int(usage.get("promptTokenCount"))
        candidate_tokens = self._nonnegative_int(usage.get("candidatesTokenCount"))
        thinking_tokens = self._nonnegative_int(usage.get("thoughtsTokenCount"))
        total_tokens = self._nonnegative_int(usage.get("totalTokenCount"))
        if input_tokens is not None and total_tokens is not None and total_tokens >= input_tokens:
            output_tokens = total_tokens - input_tokens
        elif candidate_tokens is not None and thinking_tokens is not None:
            output_tokens = candidate_tokens + thinking_tokens
        else:
            output_tokens = candidate_tokens
        actual_cost = self._actual_cost(input_tokens, output_tokens)
        response_id = parsed.get("responseId")
        if not isinstance(response_id, str) or not response_id.strip():
            response_id = None

        try:
            artifact_ref = self._artifacts.put(
                namespace="gemini-generate-content",
                content=response_body,
                content_type="application/json",
            )
        except Exception:
            return ProviderSendResult(
                outcome="unknown",
                provider_request_id=response_id,
                actual_input_tokens=input_tokens,
                actual_output_tokens=output_tokens,
                actual_cost_usd=actual_cost,
                http_status=status,
                error_classification="response_artifact_persistence_failed",
            )

        return ProviderSendResult(
            outcome="completed",
            provider_request_id=response_id,
            response_artifact_ref=artifact_ref,
            actual_input_tokens=input_tokens,
            actual_output_tokens=output_tokens,
            actual_cost_usd=actual_cost,
            http_status=status,
        )

    def lookup(
        self,
        *,
        provider_request_id: str | None,
        idempotency_key: str,
        payload_sha256: str,
    ) -> ProviderLookupResult:
        # Gemini generateContent does not expose an authoritative lookup contract.
        return ProviderLookupResult(status="unknown")

    def _post(self, url: str, body: bytes) -> tuple[bytes, int, dict[str, str]]:
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "YJ64-Engineering-Core",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                response_body = response.read(self.max_response_bytes + 1)
                headers = {
                    str(key).lower(): str(value)
                    for key, value in getattr(response, "headers", {}).items()
                }
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            response_body = exc.read(min(self.max_response_bytes, 8192))
            headers = {str(key).lower(): str(value) for key, value in exc.headers.items()}
        if not isinstance(response_body, bytes) or len(response_body) > self.max_response_bytes:
            raise OSError("Gemini response exceeded the configured byte limit")
        return response_body, status, headers

    def _model_url(self, method: str) -> str:
        return (
            self.base_url + "/models/"
            + urllib.parse.quote(self.model, safe="-._")
            + ":" + method
        )

    @staticmethod
    def _decode_request(payload: bytes) -> dict:
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("request payload must be non-empty bytes")
        try:
            body = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("request payload must be UTF-8 JSON") from None
        if not isinstance(body, dict) or not isinstance(body.get("contents"), list):
            raise ValueError("Gemini request must contain a contents array")
        return body

    @staticmethod
    def _error_message(body: bytes) -> str:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        error = parsed.get("error") if isinstance(parsed, dict) else None
        message = error.get("message", "") if isinstance(error, dict) else ""
        return message if isinstance(message, str) else ""

    @staticmethod
    def _nonnegative_int(value) -> int | None:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return None
        return value

    def _actual_cost(
        self, input_tokens: int | None, output_tokens: int | None
    ) -> str | None:
        if (
            input_tokens is None or output_tokens is None
            or self.profile.input_cost_per_million_usd is None
            or self.profile.output_cost_per_million_usd is None
        ):
            return None
        total = (
            Decimal(input_tokens) * Decimal(str(self.profile.input_cost_per_million_usd))
            + Decimal(output_tokens) * Decimal(str(self.profile.output_cost_per_million_usd))
        ) / Decimal(1_000_000)
        return format(total.quantize(Decimal("0.00000001")), "f")
