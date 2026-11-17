"""Provider lookup coordinator for the worker's reconciliation path."""
from __future__ import annotations

from collections.abc import Mapping

from .provider_adapters import ProviderLookupResult
from .worker import ProviderReconciliationDecision


class ProviderReconciliationCoordinator:
    """Look up each ambiguous reservation without ever issuing a new request.

    Only adapters explicitly registered by provider name are invoked. Missing
    adapters and inconclusive lookups produce no decision, leaving the request
    in the reconciliation queue for later/manual resolution.
    """

    def __init__(self, adapters: Mapping[str, object]) -> None:
        if not isinstance(adapters, Mapping):
            raise ValueError("adapters must be a mapping")
        normalized = {}
        for provider, adapter in adapters.items():
            if not isinstance(provider, str) or not provider.strip():
                raise ValueError("provider names must be non-empty strings")
            if not callable(getattr(adapter, "lookup", None)):
                raise ValueError("each adapter must provide lookup()")
            key = provider.strip().lower()
            if key in normalized:
                raise ValueError("provider names must be unique ignoring case")
            normalized[key] = adapter
        self._adapters = normalized

    def __call__(self, task, unknown_requests, recovered_results, context):
        decisions = []
        for request in unknown_requests:
            if not isinstance(request, dict):
                continue
            reservation_id = request.get("reservation_id")
            provider = request.get("provider")
            if not isinstance(reservation_id, str) or not reservation_id.strip():
                continue
            if not isinstance(provider, str):
                continue
            adapter = self._adapters.get(provider.strip().lower())
            if adapter is None:
                continue
            result = adapter.lookup(
                provider_request_id=request.get("provider_request_id"),
                idempotency_key=request.get("idempotency_key", ""),
                payload_sha256=request.get("payload_sha256", ""),
            )
            if not isinstance(result, ProviderLookupResult):
                raise TypeError("provider lookup adapter must return ProviderLookupResult")
            if result.status == "unknown":
                continue
            if result.status == "found":
                decisions.append(ProviderReconciliationDecision(
                    reservation_id=reservation_id,
                    outcome="provider_found",
                    evidence_ref=result.evidence_ref,
                    provider_result_ref=result.response_artifact_ref,
                    provider_request_id=result.provider_request_id,
                    input_tokens_actual=result.actual_input_tokens,
                    output_tokens_actual=result.actual_output_tokens,
                    actual_cost_usd=result.actual_cost_usd,
                ))
            elif result.status == "not_found":
                decisions.append(ProviderReconciliationDecision(
                    reservation_id=reservation_id,
                    outcome="provider_not_found",
                    evidence_ref=result.evidence_ref,
                    provider_request_id=result.provider_request_id,
                ))
        return decisions
