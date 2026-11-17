import json
import unittest
from hashlib import sha256

from yj64_engineering_core.automation.mock_provider import (
    InMemoryArtifactStore,
    MockProviderAdapter,
)
from yj64_engineering_core.automation.provider_adapters import ProviderRequest
from yj64_engineering_core.automation.provider_budget import ProviderLimitProfile


class MockProviderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.profile = ProviderLimitProfile(
            provider="mock",
            model="mock-model",
            endpoint="/mock/responses",
            requests_per_minute=10,
            tokens_per_minute=10000,
            max_concurrency=2,
            max_input_tokens=8000,
            max_output_tokens=2000,
            max_payload_bytes=100000,
        )
        self.artifacts = InMemoryArtifactStore()
        self.adapter = MockProviderAdapter(
            profile=self.profile,
            artifact_store=self.artifacts,
        )

    def request(self, payload=b'{"input":"hello"}', key="task-1-call-1"):
        return ProviderRequest(
            provider="mock",
            model="mock-model",
            endpoint="/mock/responses",
            idempotency_key=key,
            payload=payload,
            payload_sha256=sha256(payload).hexdigest(),
            input_tokens=5,
            max_output_tokens=128,
        )

    def test_adapter_exposes_explicit_test_capabilities_and_profile(self):
        self.assertEqual(self.adapter.get_limit_profile(), self.profile)
        self.assertTrue(self.adapter.capabilities.idempotency_keys)
        self.assertTrue(self.adapter.capabilities.lookup_by_idempotency_key)
        self.assertFalse(self.adapter.capabilities.streaming)

    def test_send_persists_full_response_before_returning_success(self):
        result = self.adapter.send_and_persist(self.request())
        self.assertEqual(result.outcome, "completed")
        self.assertTrue(result.response_artifact_ref.startswith("memory-artifact://"))
        stored = self.artifacts.get(result.response_artifact_ref)
        decoded = json.loads(stored.decode("utf-8"))
        self.assertTrue(decoded["mock"])
        self.assertEqual(decoded["input"], {"input": "hello"})
        metadata = self.artifacts.metadata(result.response_artifact_ref)
        self.assertEqual(metadata.sha256, sha256(stored).hexdigest())
        self.assertEqual(metadata.size_bytes, len(stored))

    def test_idempotent_resend_returns_same_artifact_without_second_write(self):
        request = self.request()
        first = self.adapter.send_and_persist(request)
        second = self.adapter.send_and_persist(request)
        self.assertEqual(first.response_artifact_ref, second.response_artifact_ref)
        self.assertEqual(first.provider_request_id, second.provider_request_id)

    def test_idempotency_key_cannot_be_reused_for_different_payload(self):
        self.adapter.send_and_persist(self.request())
        with self.assertRaisesRegex(ValueError, "different payload"):
            self.adapter.send_and_persist(
                self.request(payload=b'{"input":"changed"}')
            )

    def test_lookup_recovers_the_durable_response_artifact(self):
        request = self.request()
        sent = self.adapter.send_and_persist(request)
        found = self.adapter.lookup(
            provider_request_id=sent.provider_request_id,
            idempotency_key=request.idempotency_key,
            payload_sha256=request.payload_sha256,
        )
        self.assertEqual(found.status, "found")
        self.assertEqual(found.response_artifact_ref, sent.response_artifact_ref)
        self.assertEqual(
            self.artifacts.get(found.response_artifact_ref),
            self.artifacts.get(sent.response_artifact_ref),
        )

    def test_lookup_reports_authoritative_absence_only_inside_mock(self):
        request = self.request()
        result = self.adapter.lookup(
            provider_request_id=None,
            idempotency_key=request.idempotency_key,
            payload_sha256=request.payload_sha256,
        )
        self.assertEqual(result.status, "not_found")
        self.assertTrue(result.evidence_ref.startswith("mock-lookup:"))

    def test_lookup_with_hash_mismatch_remains_unknown(self):
        request = self.request()
        self.adapter.send_and_persist(request)
        result = self.adapter.lookup(
            provider_request_id=None,
            idempotency_key=request.idempotency_key,
            payload_sha256="0" * 64,
        )
        self.assertEqual(result.status, "unknown")

    def test_request_must_match_configured_mock_profile(self):
        request = self.request()
        wrong = ProviderRequest(
            provider="other",
            model=request.model,
            endpoint=request.endpoint,
            idempotency_key=request.idempotency_key,
            payload=request.payload,
            payload_sha256=request.payload_sha256,
            input_tokens=request.input_tokens,
            max_output_tokens=request.max_output_tokens,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.adapter.send_and_persist(wrong)


if __name__ == "__main__":
    unittest.main()
