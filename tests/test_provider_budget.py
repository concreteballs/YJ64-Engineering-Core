import unittest
from datetime import datetime, timedelta, timezone

from yj64_engineering_core.automation.provider_budget import (
    ProviderLimitProfile,
    plan_provider_capacity,
)


class ProviderBudgetTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 17, 16, 0, tzinfo=timezone.utc)

    def reservation(self, seconds_ago, tokens, state="completed", expires_in=None):
        created = self.now - timedelta(seconds=seconds_ago)
        return {
            "created_at": created,
            "estimated_tokens": tokens,
            "state": state,
            "expires_at": self.now + timedelta(seconds=expires_in) if expires_in is not None else None,
        }

    def test_rpm_window_schedules_until_oldest_request_expires(self):
        profile = ProviderLimitProfile("p", "m", "/v1", requests_per_minute=2)
        result = plan_provider_capacity(
            profile, input_tokens=10, reservations=[
                self.reservation(30, 10), self.reservation(10, 10)
            ], now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.action, "schedule_retry")
        self.assertEqual(result.retry_at, self.now + timedelta(seconds=30))
        self.assertEqual(result.requests_in_window, 2)

    def test_tpm_window_waits_until_enough_tokens_roll_off(self):
        profile = ProviderLimitProfile("p", "m", "/v1", tokens_per_minute=100)
        result = plan_provider_capacity(
            profile, input_tokens=60, reservations=[
                self.reservation(40, 60), self.reservation(10, 50)
            ], now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.retry_at, self.now + timedelta(seconds=50))
        self.assertEqual(result.tokens_in_window, 110)

    def test_concurrency_counts_live_requests_older_than_one_minute(self):
        profile = ProviderLimitProfile("p", "m", "/v1", max_concurrency=1)
        result = plan_provider_capacity(
            profile, input_tokens=1,
            reservations=[self.reservation(120, 1, state="accepted", expires_in=20)],
            now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.active_requests, 1)
        self.assertEqual(result.retry_at, self.now + timedelta(seconds=5))

    def test_single_request_over_input_or_tpm_limit_must_be_split(self):
        input_limited = plan_provider_capacity(
            ProviderLimitProfile("p", "m", "/v1", max_input_tokens=10),
            input_tokens=11, now=self.now,
        )
        self.assertEqual(input_limited.action, "split_or_decompose")
        tpm_limited = plan_provider_capacity(
            ProviderLimitProfile("p", "m", "/v1", tokens_per_minute=10),
            input_tokens=11, now=self.now,
        )
        self.assertEqual(tpm_limited.action, "split_or_decompose")

    def test_payload_byte_limit_is_independent_of_token_limit(self):
        result = plan_provider_capacity(
            ProviderLimitProfile("p", "m", "/v1", max_input_tokens=1000, max_payload_bytes=100),
            input_tokens=10, payload_bytes=101, now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.action, "split_or_decompose")
        self.assertIn("byte", result.reason)

    def test_output_limit_is_distinct(self):
        result = plan_provider_capacity(
            ProviderLimitProfile("p", "m", "/v1", max_output_tokens=5),
            input_tokens=1, output_tokens=6, now=self.now,
        )
        self.assertEqual(result.action, "reduce_output_limit")

    def test_completed_reservations_count_for_rpm_but_not_concurrency(self):
        profile = ProviderLimitProfile("p", "m", "/v1", requests_per_minute=1, max_concurrency=1)
        result = plan_provider_capacity(
            profile, input_tokens=1,
            reservations=[self.reservation(20, 1, state="completed")],
            now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.active_requests, 0)

    def test_unlimited_profile_allows_request(self):
        result = plan_provider_capacity(
            ProviderLimitProfile("p", "m", "/v1"),
            input_tokens=100000, output_tokens=1000, now=self.now,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.action, "send")

    def test_unsent_reservation_uses_concurrency_but_not_rpm_or_tpm(self):
        profile = ProviderLimitProfile(
            "p", "m", "/v1", requests_per_minute=1,
            tokens_per_minute=100, max_concurrency=2,
        )
        result = plan_provider_capacity(
            profile, input_tokens=40,
            reservations=[{
                "created_at": self.now - timedelta(seconds=5),
                "estimated_tokens": 90,
                "state": "reserved",
                "expires_at": self.now + timedelta(seconds=30),
                "sent_at": None,
            }],
            now=self.now,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.requests_in_window, 0)
        self.assertEqual(result.tokens_in_window, 0)
        self.assertEqual(result.active_requests, 1)

    def test_unknown_sent_request_remains_in_concurrency_after_ttl(self):
        profile = ProviderLimitProfile("p", "m", "/v1", max_concurrency=1)
        result = plan_provider_capacity(
            profile, input_tokens=1,
            reservations=[{
                "created_at": self.now - timedelta(minutes=10),
                "estimated_tokens": 1,
                "state": "unknown",
                "expires_at": None,
                "sent_at": self.now - timedelta(minutes=10),
            }],
            now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.active_requests, 1)
        self.assertEqual(result.action, "hold_for_review")
        self.assertIsNone(result.retry_at)

    def test_live_sending_request_uses_short_scheduler_recheck(self):
        profile = ProviderLimitProfile("p", "m", "/v1", max_concurrency=1)
        result = plan_provider_capacity(
            profile, input_tokens=1,
            reservations=[{
                "created_at": self.now - timedelta(seconds=10),
                "estimated_tokens": 1,
                "state": "sending",
                "expires_at": None,
                "sent_at": self.now - timedelta(seconds=10),
            }],
            now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.action, "schedule_retry")
        self.assertEqual(result.retry_at, self.now + timedelta(seconds=5))

    def test_completed_sent_reservation_counts_in_rolling_usage(self):
        profile = ProviderLimitProfile("p", "m", "/v1", requests_per_minute=1)
        result = plan_provider_capacity(
            profile, input_tokens=1,
            reservations=[{
                "created_at": self.now - timedelta(seconds=15),
                "estimated_tokens": 20,
                "state": "completed",
                "sent_at": self.now - timedelta(seconds=15),
            }],
            now=self.now,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.requests_in_window, 1)

    def test_invalid_reservation_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_provider_capacity(
                ProviderLimitProfile("p", "m", "/v1"),
                input_tokens=1, reservations=[{"created_at": "not-a-date"}],
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
