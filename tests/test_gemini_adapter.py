import io
import json
import unittest
import urllib.error
from hashlib import sha256

from yj64_engineering_core.automation.gemini_adapter import GeminiGenerateContentAdapter
from yj64_engineering_core.automation.provider_adapters import ProviderRequest
from yj64_engineering_core.automation.provider_budget import ProviderLimitProfile


class FakeResponse:
    status = 200

    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


class FakeArtifactStore:
    def __init__(self, fail=False):
        self.fail = fail
        self.items = {}

    def put(self, *, namespace, content, content_type):
        if self.fail:
            raise OSError("storage unavailable")
        ref = f"artifact://{namespace}/{sha256(content).hexdigest()}"
        self.items[ref] = (content, content_type)
        return ref


class GeminiAdapterTests(unittest.TestCase):
    def setUp(self):
        self.model = "gemini-2.5-flash"
        self.profile = ProviderLimitProfile(
            provider="gemini",
            model=self.model,
            endpoint="generateContent",
            max_concurrency=1,
            max_input_tokens=100000,
            max_output_tokens=1024,
            max_payload_bytes=2_000_000,
            input_cost_per_million_usd=0.1,
            output_cost_per_million_usd=0.4,
        )
        self.artifacts = FakeArtifactStore()

    def adapter(self, opener):
        return GeminiGenerateContentAdapter(
            model=self.model,
            limit_profile=self.profile,
            artifact_store=self.artifacts,
            api_key="test-api-key",
            opener=opener,
        )

    def request(self):
        payload = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": "Analyze this CI log."}]}],
            "generationConfig": {
                "maxOutputTokens": 256,
                "responseMimeType": "application/json",
            },
        }, separators=(",", ":")).encode()
        return ProviderRequest(
            provider="gemini",
            model=self.model,
            endpoint="generateContent",
            idempotency_key="ci-log-task-17",
            payload=payload,
            payload_sha256=sha256(payload).hexdigest(),
            input_tokens=15,
            max_output_tokens=256,
        )

    def test_count_tokens_uses_model_bound_generate_content_request(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["key"] = request.get_header("X-goog-api-key")
            captured["body"] = json.loads(request.data.decode())
            return FakeResponse(b'{"totalTokens":321}')

        count = self.adapter(opener).count_tokens(self.request().payload)
        self.assertEqual(count, 321)
        self.assertTrue(captured["url"].endswith("/models/gemini-2.5-flash:countTokens"))
        self.assertEqual(captured["key"], "test-api-key")
        self.assertEqual(
            captured["body"]["generateContentRequest"]["model"],
            "models/gemini-2.5-flash",
        )

    def test_success_is_persisted_before_completed_result(self):
        body = json.dumps({
            "responseId": "response-123",
            "candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 5,
            },
        }).encode()

        result = self.adapter(lambda request, timeout: FakeResponse(body)).send_and_persist(
            self.request()
        )
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.actual_input_tokens, 100)
        self.assertEqual(result.actual_output_tokens, 25)
        self.assertEqual(result.actual_cost_usd, "0.00002000")
        self.assertIn(result.response_artifact_ref, self.artifacts.items)

    def test_rate_limit_is_classified_without_internal_retry(self):
        error = urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com/",
            429,
            "Too Many Requests",
            {"Retry-After": "30"},
            io.BytesIO(b'{"error":{"message":"rate limit"}}'),
        )

        def opener(request, timeout):
            raise error

        result = self.adapter(opener).send_and_persist(self.request())
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.http_status, 429)
        self.assertEqual(result.error_classification, "rate_limited")
        self.assertEqual(result.retry_after_seconds, 30.0)

    def test_transport_failure_is_unknown_not_retryable_failure(self):
        def opener(request, timeout):
            raise TimeoutError("network timeout")

        result = self.adapter(opener).send_and_persist(self.request())
        self.assertEqual(result.outcome, "unknown")
        self.assertEqual(result.error_classification, "ambiguous_transport_outcome")

    def test_artifact_failure_keeps_successful_send_ambiguous(self):
        artifacts = FakeArtifactStore(fail=True)
        adapter = GeminiGenerateContentAdapter(
            model=self.model,
            limit_profile=self.profile,
            artifact_store=artifacts,
            api_key="test-api-key",
            opener=lambda request, timeout: FakeResponse(
                b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'
            ),
        )
        result = adapter.send_and_persist(self.request())
        self.assertEqual(result.outcome, "unknown")
        self.assertEqual(result.error_classification, "response_artifact_persistence_failed")

    def test_gemini_has_no_authoritative_lookup_or_idempotency(self):
        adapter = self.adapter(lambda request, timeout: FakeResponse(b'{"totalTokens":1}'))
        self.assertFalse(adapter.capabilities.idempotency_keys)
        self.assertFalse(adapter.capabilities.lookup_by_request_id)
        self.assertEqual(
            adapter.lookup(
                provider_request_id="response-123",
                idempotency_key="ci-log-task-17",
                payload_sha256=self.request().payload_sha256,
            ).status,
            "unknown",
        )

    def test_rejects_profile_for_a_different_model(self):
        other = ProviderLimitProfile(
            provider="gemini", model="other-model", endpoint="generateContent",
            max_concurrency=1,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            GeminiGenerateContentAdapter(
                model=self.model, limit_profile=other,
                artifact_store=self.artifacts, api_key="test",
            )


if __name__ == "__main__":
    unittest.main()
