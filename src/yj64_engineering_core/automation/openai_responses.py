"""OpenAI Responses API lookup adapter for ambiguous request reconciliation.

This adapter only retrieves an existing response by its provider-issued ID.
It never submits or retries model requests. A missing ID, 404, transport error,
or non-terminal response is UNKNOWN, never proof that a request was not sent.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Protocol

from .provider_adapters import ProviderCapabilities, ProviderLookupResult


class ArtifactWriter(Protocol):
    def put(self, *, namespace: str, content: bytes, content_type: str) -> str: ...


_RESPONSE_ID_RE = re.compile(r"^resp_[A-Za-z0-9_-]{8,200}$")


class OpenAIResponsesLookupAdapter:
    """Retrieve an existing OpenAI Responses API object and persist it durably."""

    provider = "openai"

    def __init__(
        self,
        *,
        artifact_store: ArtifactWriter,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_response_bytes: int = 6 * 1024 * 1024,
        opener: Callable | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        if not callable(getattr(artifact_store, "put", None)):
            raise ValueError("artifact_store must provide put()")
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("OPENAI_API_KEY is required")
        parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.openai.com"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/v1")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be the official OpenAI API HTTPS origin")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes < 1024
        ):
            raise ValueError("max_response_bytes must be at least 1024")
        self._artifacts = artifact_store
        self._api_key = key.strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self._opener = opener or urllib.request.urlopen
        self._base_url = "https://api.openai.com/v1"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            idempotency_keys=False,
            lookup_by_request_id=True,
            lookup_by_idempotency_key=False,
            streaming=False,
            remote_file_ingestion=False,
            stateful_conversations=False,
            detailed_usage=True,
        )

    def lookup(
        self,
        *,
        provider_request_id: str | None,
        idempotency_key: str,
        payload_sha256: str,
    ) -> ProviderLookupResult:
        # The idempotency key and payload hash are retained by the caller for
        # audit/correlation. OpenAI's retrieve endpoint requires response_id;
        # neither value is treated as a substitute for that identifier.
        if not isinstance(provider_request_id, str) or not _RESPONSE_ID_RE.fullmatch(
            provider_request_id
        ):
            return ProviderLookupResult(status="unknown")

        url = self._base_url + "/responses/" + urllib.parse.quote(
            provider_request_id, safe=""
        )
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                if getattr(response, "status", 200) != 200:
                    return ProviderLookupResult(status="unknown")
                body = response.read(self.max_response_bytes + 1)
            if not isinstance(body, bytes) or not body or len(body) > self.max_response_bytes:
                return ProviderLookupResult(status="unknown")
            payload = json.loads(body.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
                UnicodeDecodeError, json.JSONDecodeError, ValueError):
            # In particular, HTTP 404 is NOT proof that the original POST was
            # never accepted: retention, project scope or access may differ.
            return ProviderLookupResult(status="unknown")
        except Exception:
            return ProviderLookupResult(status="unknown")

        if not isinstance(payload, dict) or payload.get("id") != provider_request_id:
            return ProviderLookupResult(status="unknown")
        status = payload.get("status")
        if status not in {"completed", "incomplete"}:
            return ProviderLookupResult(status="unknown")

        try:
            artifact_ref = self._artifacts.put(
                namespace="openai-responses-reconciliation",
                content=body,
                content_type="application/json",
            )
        except Exception:
            # A result is not considered recovered until its full response is
            # durably persisted and can be resumed after a process restart.
            return ProviderLookupResult(status="unknown")

        usage = payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) or input_tokens < 0:
            input_tokens = None
        if not isinstance(output_tokens, int) or isinstance(output_tokens, bool) or output_tokens < 0:
            output_tokens = None

        digest = hashlib.sha256(body).hexdigest()
        return ProviderLookupResult(
            status="found",
            evidence_ref="openai-responses-lookup:sha256:" + digest,
            provider_request_id=provider_request_id,
            response_artifact_ref=artifact_ref,
            actual_input_tokens=input_tokens,
            actual_output_tokens=output_tokens,
        )
