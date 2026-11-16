import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class FakeCursor:
    def __init__(self, already_seen=False, claim_row=None, returned_state=None, rowcount=1):
        self.already_seen = already_seen
        self.claim_row = claim_row
        self.returned_state = returned_state
        self.rowcount = rowcount
        self.statements = []
        self._fetch = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.statements.append((query, params))
        if "INSERT INTO yj64_ci_events" in query:
            self._fetch = None if self.already_seen else (73,)
        elif "RETURNING task.task_id" in query:
            self._fetch = self.claim_row
        elif "RETURNING state" in query:
            self._fetch = (self.returned_state,) if self.returned_state else None

    def fetchone(self):
        return self._fetch


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.fake_cursor


class PostgresCycleStoreTests(unittest.TestCase):
    def event(self):
        return {
            "event": "yj64.ci.completed",
            "repository": "concreteballs/YJ64-Engineering-Core",
            "workflow": "Python tests",
            "run_id": 123,
            "run_attempt": 1,
            "conclusion": "success",
            "commit_sha": "a" * 40,
            "branch": "main",
            "run_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/123",
        }

    def store(self, cursor):
        return PostgresCycleStore("postgresql://test", lambda _: FakeConnection(cursor))

    def test_new_event_is_persisted_and_enqueued(self):
        cursor = FakeCursor()
        result = self.store(cursor).record_ci_event(self.event())
        self.assertEqual(result, {
            "accepted": True, "duplicate": False, "event_id": 73, "task_enqueued": True
        })
        self.assertEqual(len(cursor.statements), 2)
        self.assertIn("yj64_task_queue", cursor.statements[1][0])
        self.assertEqual(cursor.statements[1][1][1], "ci-event:concreteballs/YJ64-Engineering-Core:123:1")

    def test_duplicate_event_does_not_enqueue_again(self):
        cursor = FakeCursor(already_seen=True)
        result = self.store(cursor).record_ci_event(self.event())
        self.assertTrue(result["duplicate"])
        self.assertFalse(result["task_enqueued"])
        self.assertEqual(len(cursor.statements), 1)

    def test_claim_uses_a_lease_and_skip_locked(self):
        cursor = FakeCursor(claim_row=(12, "process_ci_event", {"event_id": 73}, 1, 3))
        task = self.store(cursor).claim_next_task("worker-a")
        self.assertEqual(task["task_id"], 12)
        self.assertEqual(task["worker_id"], "worker-a")
        self.assertIn("FOR UPDATE SKIP LOCKED", cursor.statements[1][0])
        self.assertEqual(task["attempts"], 1)

    def test_claim_validates_lease(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).claim_next_task("worker-a", lease_seconds=2)

    def test_complete_requires_current_lease_owner(self):
        cursor = FakeCursor(rowcount=1)
        self.assertTrue(self.store(cursor).complete_task(12, "worker-a"))
        self.assertIn("lock_owner = %s", cursor.statements[0][0])

    def test_fail_retries_with_bounded_delay(self):
        cursor = FakeCursor(returned_state="pending")
        state = self.store(cursor).fail_task(12, "worker-a", "temporary error", 90)
        self.assertEqual(state, "pending")
        self.assertEqual(cursor.statements[0][1][0], 90)

    def test_rejects_missing_event_fields(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).record_ci_event({"run_id": 1})


if __name__ == "__main__":
    unittest.main()
