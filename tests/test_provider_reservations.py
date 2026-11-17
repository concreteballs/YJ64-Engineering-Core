import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class ReservationCursor:
    def __init__(self, *, profile=True, duplicate=None, task=None):
        self.profile = profile
        self.duplicate = duplicate
        self.task = task or (
            "running", "worker-a", None,
            None, None, None, 0, 0, 0, 0, 0, 0,
        )
        self.one = None
        self.many = []
        self.rowcount = 1
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        self.one = None
        self.many = []
        self.rowcount = 1
        if "SELECT state, lock_owner, locked_at" in query:
            self.one = self.task
        elif "SELECT reservation_id, state, queue_task_id" in query:
            self.one = self.duplicate
        elif "FROM yj64_provider_limit_profiles" in query:
            self.one = (
                10, 1000, 2, 800, 200, True, 1.0, 2.0
            ) if self.profile else None
        elif "FROM yj64_provider_request_reservations" in query and "SELECT created_at" in query:
            self.many = []
        elif "FROM yj64_cycle_usage_budget" in query:
            self.one = None
        elif "INSERT INTO yj64_provider_request_reservations" in query:
            self.rowcount = 1
        elif "UPDATE yj64_task_queue" in query:
            self.rowcount = 1

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class ReservationConnection:
    def __init__(self, cursor):
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.value


class ProviderReservationTests(unittest.TestCase):
    def store(self, cursor):
        return PostgresCycleStore(
            "postgresql://test", lambda _: ReservationConnection(cursor)
        )

    def reserve(self, store, key="task-9:model-call-1"):
        return store.reserve_provider_capacity(
            9, "worker-a", key, provider="provider-a", model="model-a",
            endpoint="/v1/responses", input_tokens=100, output_tokens=40,
        )

    def test_reservation_locks_task_and_provider_profile_then_persists(self):
        cursor = ReservationCursor()
        result = self.reserve(self.store(cursor))
        self.assertTrue(result["reserved"])
        self.assertFalse(result["duplicate"])
        self.assertTrue(any("FOR UPDATE" in q and "yj64_task_queue" in q for q, _ in cursor.statements))
        self.assertTrue(any("FOR UPDATE" in q and "yj64_provider_limit_profiles" in q for q, _ in cursor.statements))
        self.assertTrue(any("INSERT INTO yj64_provider_request_reservations" in q for q, _ in cursor.statements))

    def test_missing_provider_profile_fails_closed(self):
        cursor = ReservationCursor(profile=False)
        result = self.reserve(self.store(cursor))
        self.assertFalse(result["reserved"])
        self.assertEqual(result["action"], "hold_for_review")
        self.assertFalse(any("INSERT INTO yj64_provider_request_reservations" in q for q, _ in cursor.statements))

    def test_idempotent_duplicate_returns_original_reservation(self):
        cursor = ReservationCursor(
            duplicate=("reservation-1", "reserved", 9, "provider-a", "model-a", "/v1/responses")
        )
        result = self.reserve(self.store(cursor))
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["reservation_id"], "reservation-1")
        self.assertFalse(any("INSERT INTO yj64_provider_request_reservations" in q for q, _ in cursor.statements))

    def test_idempotency_key_cannot_be_reused_for_another_task(self):
        cursor = ReservationCursor(
            duplicate=("reservation-1", "reserved", 10, "provider-a", "model-a", "/v1/responses")
        )
        with self.assertRaisesRegex(ValueError, "different task or provider request"):
            self.reserve(self.store(cursor))

    def test_task_budget_blocks_before_reserving(self):
        cursor = ReservationCursor(task=(
            "running", "worker-a", None,
            50, 100, None, 0, 0, 0, 0, 0, 0,
        ))
        result = self.reserve(self.store(cursor))
        self.assertFalse(result["reserved"])
        self.assertEqual(result["action"], "task_budget_exhausted")
        self.assertFalse(any("INSERT INTO yj64_provider_request_reservations" in q for q, _ in cursor.statements))


if __name__ == "__main__":
    unittest.main()
