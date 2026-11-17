import json
import unittest
from urllib.error import HTTPError, URLError
from io import BytesIO

from yj64_engineering_core.automation.openai_responses import OpenAIResponsesLookupAdapter
from yj64_engineering_core.automation.provider_adapters import ProviderLookupResult
from yj64_engineering_core.automation.provider_reconciliation import ProviderReconciliationCoordinator


class MemoryArtifacts:
    def __init__(self):
        self.items = {}

    def put(self, *, namespace, content, content_type):
        ref = "test-artifact://" + namespace + "/" + str(len(self.items) + 1)
        self.items[ref] = (content, content_type)
        return ref


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


class OpenAIResponsesLookupTests(unittest.TestCase):
    def setUp(self):
        self.artifacts = MemoryArtifacts()
        self.payload = {
            "id": "resp_1234567890abcdef",
            "status": "completed",
            "usage": {"input_tokens": 17, "output_tokens": 29},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "recovered"}]}],
        }
        self.body = json.dumps(self.payload).encode()

    def adapter(self, opener):
        return OpenAIResponsesLookupAdapter(
            artifact_store=self.artifacts,
            api_key="test-key",
            opener=opener,
        )

    def lookup(self, adapter=None, request_id="resp_1234567890abcdef"):
        adapter = adapter or self.adapter(lambda request, timeout: FakeResponse(self.body))
        return adapter.lookup(
            provider_request_id=request_id,
            idempotency_key="stable-key",
            payload_sha256="a" * 64,
        )

    def test_completed_response_is_persisted_before_found(self):
        result = self.lookup()
        self.assertEqual(result.status, "found")
        self.assertEqual(result.provider_request_id, self.payload["id"])
        self.assertEqual(result.actual_input_tokens, 17)
        self.assertEqual(result.actual_output_tokens, 29)
        self.assertIn(result.response_artifact_ref, self.artifacts.items)
        self.assertEqual(self.artifacts.items[result.response_artifact_ref][0], self.body)
        self.assertTrue(result.evidence_ref.startswith("openai-responses-lookup:sha256:"))

    def test_missing_response_id_never_uses_idempotency_key_as_lookup(self):
        result = self.lookup(request_id=None)
        self.assertEqual(result.status, "unknown")

    def test_in_progress_response_remains_unknown(self):
        payload = dict(self.payload, status="in_progress")
        body = json.dumps(payload).encode()
        result = self.lookup(self.adapter(lambda request, timeout: FakeResponse(body)))
        self.assertEqual(result.status, "unknown")
        self.assertEqual(self.artifacts.items, {})

    def test_http_404_is_unknown_not_authoritative_not_found(self):
        def missing(request, timeout):
            raise HTTPError(request.full_url, 404, "not found", {}, BytesIO(b""))
        result = self.lookup(self.adapter(missing))
        self.assertEqual(result.status, "unknown")

    def test_transport_error_is_unknown(self):
        result = self.lookup(self.adapter(
            lambda request, timeout: (_ for _ in ()).throw(URLError("offline"))
        ))
        self.assertEqual(result.status, "unknown")

    def test_response_id_mismatch_is_unknown(self):
        payload = dict(self.payload, id="resp_other123456789")
        body = json.dumps(payload).encode()
        result = self.lookup(self.adapter(lambda request, timeout: FakeResponse(body)))
        self.assertEqual(result.status, "unknown")

    def test_oversized_response_is_unknown(self):
        result = self.lookup(self.adapter(
            lambda request, timeout: FakeResponse(self.body + b" " * 2048)
        ))
        # The adapter's default bound is much larger; use a deliberately small bound.
        small = OpenAIResponsesLookupAdapter(
            artifact_store=self.artifacts, api_key="test-key",
            opener=lambda request, timeout: FakeResponse(self.body),
            max_response_bytes=1024,
        )
        result = small.lookup(
            provider_request_id=self.payload["id"],
            idempotency_key="stable-key",
            payload_sha256="a" * 64,
        )
        self.assertEqual(result.status, "unknown")

    def test_artifact_write_failure_is_unknown(self):
        class BrokenArtifacts:
            def put(self, **kwargs):
                raise RuntimeError("storage unavailable")
        adapter = OpenAIResponsesLookupAdapter(
            artifact_store=BrokenArtifacts(), api_key="test-key",
            opener=lambda request, timeout: FakeResponse(self.body),
        )
        result = self.lookup(adapter)
        self.assertEqual(result.status, "unknown")

    def test_adapter_sends_only_authenticated_get_to_official_host(self):
        seen = {}
        def opener(request, timeout):
            seen["method"] = request.get_method()
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            return FakeResponse(self.body)
        self.lookup(self.adapter(opener))
        self.assertEqual(seen["method"], "GET")
        self.assertTrue(seen["url"].startswith("https://api.openai.com/v1/responses/"))
        self.assertEqual(seen["auth"], "Bearer test-key")

    def test_capabilities_do_not_claim_lookup_by_idempotency_key(self):
        caps = self.adapter(lambda request, timeout: FakeResponse(self.body)).capabilities
        self.assertTrue(caps.lookup_by_request_id)
        self.assertFalse(caps.lookup_by_idempotency_key)


class ProviderReconciliationCoordinatorTests(unittest.TestCase):
    def test_only_authoritative_found_results_become_decisions(self):
        class Adapter:
            def __init__(self):
                self.ids = []
            def lookup(self, **kwargs):
                self.ids.append(kwargs["provider_request_id"])
                if kwargs["provider_request_id"] == "resp_1234567890abcdef":
                    return ProviderLookupResult(
                        status="found", evidence_ref="evidence:ok",
                        provider_request_id=kwargs["provider_request_id"],
                        response_artifact_ref="artifact:response",
                        actual_input_tokens=5, actual_output_tokens=8,
                    )
                return ProviderLookupResult(status="unknown")
        adapter = Adapter()
        coordinator = ProviderReconciliationCoordinator({"OpenAI": adapter})
        requests = [
            {"reservation_id": "r1", "provider": "openai",
             "provider_request_id": "resp_1234567890abcdef",
             "idempotency_key": "k1", "payload_sha256": "a" * 64},
            {"reservation_id": "r2", "provider": "openai",
             "provider_request_id": None, "idempotency_key": "k2",
             "payload_sha256": "b" * 64},
            {"reservation_id": "r3", "provider": "anthropic",
             "provider_request_id": "msg_123456789"},
        ]
        decisions = coordinator({}, requests, [], None)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].reservation_id, "r1")
        self.assertEqual(decisions[0].outcome, "provider_found")
        self.assertEqual(adapter.ids, ["resp_1234567890abcdef", None])

    def test_authoritative_not_found_is_passed_through(self):
        class Adapter:
            def lookup(self, **kwargs):
                return ProviderLookupResult(
                    status="not_found", evidence_ref="evidence:absence"
                )
        coordinator = ProviderReconciliationCoordinator({"example": Adapter()})
        decisions = coordinator({}, [{
            "reservation_id": "r1", "provider": "example",
            "provider_request_id": "id", "idempotency_key": "key",
            "payload_sha256": "hash",
        }], [], None)
        self.assertEqual(decisions[0].outcome, "provider_not_found")

    def test_missing_provider_adapter_leaves_request_unresolved(self):
        coordinator = ProviderReconciliationCoordinator({})
        decisions = coordinator({}, [{
            "reservation_id": "r1", "provider": "anthropic",
            "provider_request_id": "msg_123",
        }], [], None)
        self.assertEqual(decisions, [])


if __name__ == "__main__":
    unittest.main()
