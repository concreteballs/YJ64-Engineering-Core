import json
import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class FakeCursor:
    def __init__(self, *, has_lease=True, inserted=True, rowcount=1, queue_state_after_update="pending"):
        self.has_lease = has_lease
        self.inserted = inserted
        self.rowcount = rowcount
        self.queue_state_after_update = queue_state_after_update
        self.statements = []
        self._fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.statements.append((query, params))
        if "SELECT task_id FROM yj64_task_queue" in query:
            self._fetch = (12,) if self.has_lease else None
        elif "INSERT INTO yj64_model_request_attempts" in query:
            self._fetch = (91,) if self.inserted else None
        elif "UPDATE yj64_task_queue" in query and "RETURNING state" in query:
            self._fetch = (self.queue_state_after_update,)
        else:
            self._fetch = None

    def fetchone(self):
        return self._fetch


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_value


class ProviderAttemptStoreTests(unittest.TestCase):
    def store(self, cursor):
        return PostgresCycleStore("postgresql://test", lambda _: FakeConnection(cursor))

    def attempt(self):
        return {
            "attempt_number": 2,
            "provider": "example-provider",
            "model": "example-model",
            "endpoint": "/v1/responses",
            "provider_request_id": "req_123",
            "error_classification": "rate_limited",
            "http_status": 429,
            "headers": {
                "Retry-After": "45",
                "X-Request-Id": "req_123",
                "Authorization": "Bearer must-not-be-stored",
                "Set-Cookie": "must-not-be-stored",
            },
        }

    def test_retry_attempt_is_recorded_and_lease_released(self):
        cursor = FakeCursor()
        result = self.store(cursor).record_model_request_attempt(
            12, "worker-a", self.attempt(),
            {"action": "schedule_retry", "delay_seconds": 45, "reason": "rate limited"},
        )
        self.assertEqual(result, {"recorded": True, "duplicate": False, "task_state": "pending"})
        insert = next(params for query, params in cursor.statements
                      if "INSERT INTO yj64_model_request_attempts" in query)
        headers = json.loads(insert[-2])
        self.assertEqual(headers, {"retry-after": "45", "x-request-id": "req_123"})
        update = cursor.statements[-1][0]
        self.assertIn("available_at = CASE", update)
        self.assertIn("lock_owner = NULL", update)

    def test_endpoint_query_string_is_not_persisted(self):
        cursor = FakeCursor()
        attempt = self.attempt()
        attempt["endpoint"] = "https://api.example.test/v1/responses?api_key=secret"
        self.store(cursor).record_model_request_attempt(
            12, "worker-a", attempt,
            {"action": "schedule_retry", "delay_seconds": 15, "reason": "rate limited"},
        )
        insert = next(params for query, params in cursor.statements
                      if "INSERT INTO yj64_model_request_attempts" in query)
        self.assertEqual(insert[4], "/v1/responses")

    def test_retry_budget_exhaustion_marks_task_failed(self):
        cursor = FakeCursor(queue_state_after_update="failed")
        result = self.store(cursor).record_model_request_attempt(
            12, "worker-a", self.attempt(),
            {"action": "schedule_retry", "delay_seconds": 45, "reason": "rate limited"},
        )
        self.assertEqual(result["task_state"], "failed")
        self.assertIn("attempts >= max_attempts", cursor.statements[-1][0])

    def test_quota_and_payload_recovery_are_blocked_not_retried_unchanged(self):
        cursor = FakeCursor()
        result = self.store(cursor).record_model_request_attempt(
            12, "worker-a", self.attempt(),
            {"action": "block_until_reset", "delay_seconds": 3600,
             "reason": "quota exhausted"},
        )
        self.assertEqual(result["task_state"], "blocked")
        self.assertIn("state = 'blocked'", cursor.statements[-1][0])

    def test_duplicate_attempt_does_not_change_task_state(self):
        cursor = FakeCursor(inserted=False)
        result = self.store(cursor).record_model_request_attempt(
            12, "worker-a", self.attempt(),
            {"action": "schedule_retry", "delay_seconds": 30},
        )
        self.assertTrue(result["duplicate"])
        self.assertEqual(len(cursor.statements), 2)

    def test_attempt_requires_live_lease(self):
        cursor = FakeCursor(has_lease=False)
        with self.assertRaisesRegex(RuntimeError, "live task lease"):
            self.store(cursor).record_model_request_attempt(
                12, "worker-a", self.attempt(),
                {"action": "schedule_retry", "delay_seconds": 30},
            )

    def test_attempt_metadata_and_retry_inputs_are_validated(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).record_model_request_attempt(
                12, "worker-a", {}, {"action": "schedule_retry", "delay_seconds": 30}
            )
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).record_model_request_attempt(
                12, "worker-a", self.attempt(),
                {"action": "schedule_retry", "delay_seconds": -1},
            )


    def test_quota_block_persists_reset_timestamp_on_queue(self):
        cursor = FakeCursor()
        attempt = self.attempt()
        attempt["error_classification"] = "quota_exhausted"
        attempt["quota_reset_at"] = "2026-11-18T00:00:00+00:00"
        result = self.store(cursor).record_model_request_attempt(
            12, "worker-a", attempt,
            {"action": "block_until_reset", "delay_seconds": 3600,
             "reason": "monthly quota exhausted"},
        )
        self.assertEqual(result["task_state"], "blocked")
        update_query, update_params = cursor.statements[-1]
        self.assertIn("blocked_reason = 'quota_exhausted'", update_query)
        self.assertIn("quota_reset_at = %s", update_query)
        self.assertEqual(update_params[0], "2026-11-18T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
