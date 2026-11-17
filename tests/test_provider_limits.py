import unittest
from datetime import datetime, timezone
from email.utils import format_datetime

from yj64_engineering_core.automation.provider_limits import classify_provider_error


class ProviderErrorClassificationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_rate_limit_honors_retry_after_and_is_retryable(self):
        result = classify_provider_error(429, headers={"Retry-After": "37"}, now=self.now)
        self.assertEqual((result.classification, result.action, result.delay_seconds),
                         ("rate_limited", "schedule_retry", 37))
        self.assertTrue(result.retryable)

    def test_rate_limit_uses_bounded_exponential_backoff_and_jitter(self):
        result = classify_provider_error(429, attempt=4, jitter_fraction=0.2, now=self.now)
        self.assertEqual(result.delay_seconds, 48)

    def test_retry_after_http_date(self):
        target = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        result = classify_provider_error(503, headers={"Retry-After": format_datetime(target)},
                                         now=self.now)
        self.assertEqual(result.delay_seconds, 60)

    def test_quota_exhaustion_blocks_instead_of_looping(self):
        result = classify_provider_error(429, "insufficient_quota: monthly quota exceeded",
                                         headers={"x-ratelimit-reset": "120"}, now=self.now)
        self.assertEqual(result.classification, "quota_exhausted")
        self.assertEqual(result.action, "block_until_reset")
        self.assertFalse(result.retryable)
        self.assertEqual(result.delay_seconds, 120)

    def test_daily_and_monthly_limits_are_blocked(self):
        for message in ("requests per day limit reached", "exceeded your current quota"):
            result = classify_provider_error(429, message, now=self.now)
            self.assertEqual(result.action, "block_until_reset")
            self.assertFalse(result.retryable)

    def test_payload_too_large_requires_split(self):
        result = classify_provider_error(413, "request too large")
        self.assertEqual(result.action, "split_or_decompose")
        self.assertFalse(result.retryable)

    def test_context_overflow_requires_smaller_rebuilt_context(self):
        result = classify_provider_error(400, "maximum context length exceeded")
        self.assertEqual(result.action, "rebuild_smaller_context")

    def test_transient_server_error_retries(self):
        result = classify_provider_error(503, attempt=2, now=self.now)
        self.assertTrue(result.retryable)
        self.assertEqual(result.delay_seconds, 10)

    def test_concurrency_limit_retries(self):
        result = classify_provider_error(None, "too many concurrent requests", attempt=2)
        self.assertEqual(result.classification, "concurrency_limited")
        self.assertEqual(result.delay_seconds, 10)

    def test_authentication_error_is_not_retried(self):
        result = classify_provider_error(401, "invalid API key")
        self.assertEqual(result.action, "fail_or_require_configuration")
        self.assertFalse(result.retryable)

    def test_unknown_error_is_held_for_review(self):
        result = classify_provider_error(499, "provider returned unusual response")
        self.assertEqual(result.action, "hold_for_review")

    def test_invalid_retry_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            classify_provider_error(429, attempt=0)
        with self.assertRaises(ValueError):
            classify_provider_error(429, jitter_fraction=0.8)


if __name__ == "__main__":
    unittest.main()
