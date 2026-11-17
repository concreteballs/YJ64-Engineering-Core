import unittest
from hashlib import sha256

from yj64_engineering_core.automation.provider_adapters import (
    ProviderCapabilities,
    ProviderLookupResult,
    ProviderRequest,
    ProviderSendResult,
)


class ProviderAdapterContractTests(unittest.TestCase):
    def request(self):
        payload = b'{"model":"m","input":"hello"}'
        return ProviderRequest(
            provider="provider-a", model="model-a", endpoint="/v1/responses",
            idempotency_key="task-1-call-1", payload=payload,
            payload_sha256=sha256(payload).hexdigest(),
            input_tokens=12, max_output_tokens=64,
        )

    def test_request_binds_exact_serialized_body_hash_and_byte_count(self):
        request = self.request()
        self.assertEqual(request.payload_bytes, len(request.payload))
        self.assertEqual(request.payload_sha256, sha256(request.payload).hexdigest())

    def test_request_rejects_hash_for_different_payload(self):
        request = self.request()
        with self.assertRaisesRegex(ValueError, "does not match"):
            ProviderRequest(
                provider=request.provider, model=request.model,
                endpoint=request.endpoint, idempotency_key=request.idempotency_key,
                payload=b'{"model":"m","input":"different"}',
                payload_sha256=request.payload_sha256,
                input_tokens=12, max_output_tokens=64,
            )

    def test_success_cannot_be_returned_before_response_artifact_is_persisted(self):
        with self.assertRaisesRegex(ValueError, "durably persisted"):
            ProviderSendResult(outcome="completed")

    def test_success_contains_only_opaque_artifact_reference(self):
        result = ProviderSendResult(
            outcome="completed",
            provider_request_id="req-1",
            response_artifact_ref="artifact://responses/req-1",
            actual_input_tokens=11,
            actual_output_tokens=23,
        )
        self.assertEqual(result.response_artifact_ref, "artifact://responses/req-1")

    def test_unknown_delivery_is_not_interpreted_as_not_found(self):
        result = ProviderLookupResult(status="unknown")
        self.assertEqual(result.status, "unknown")
        with self.assertRaisesRegex(ValueError, "evidence reference"):
            ProviderLookupResult(status="not_found")

    def test_found_lookup_requires_result_artifact(self):
        with self.assertRaisesRegex(ValueError, "durable response artifact"):
            ProviderLookupResult(status="found", evidence_ref="lookup-event-1")

    def test_capability_flags_are_explicit_booleans(self):
        capabilities = ProviderCapabilities(
            idempotency_keys=True, lookup_by_request_id=True,
            lookup_by_idempotency_key=False,
        )
        self.assertTrue(capabilities.idempotency_keys)
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            ProviderCapabilities(streaming="yes")


if __name__ == "__main__":
    unittest.main()
