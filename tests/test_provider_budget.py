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
        self.assertEqual(result.retry_at, self.now + timedelta(seconds=20))

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

    def test_invalid_reservation_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_provider_capacity(
                ProviderLimitProfile("p", "m", "/v1"),
                input_tokens=1, reservations=[{"created_at": "not-a-date"}],
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
