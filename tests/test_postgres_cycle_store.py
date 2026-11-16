import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class FakeCursor:
    def __init__(self, already_seen=False):
        self.already_seen = already_seen
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

    def test_new_event_is_persisted_and_enqueued(self):
        cursor = FakeCursor()
        store = PostgresCycleStore("postgresql://test", lambda _: FakeConnection(cursor))
        result = store.record_ci_event(self.event())
        self.assertEqual(result, {
            "accepted": True, "duplicate": False, "event_id": 73, "task_enqueued": True
        })
        self.assertEqual(len(cursor.statements), 2)
        self.assertIn("yj64_task_queue", cursor.statements[1][0])
        self.assertEqual(cursor.statements[1][1][1], "ci-event:concreteballs/YJ64-Engineering-Core:123:1")

    def test_duplicate_event_does_not_enqueue_again(self):
        cursor = FakeCursor(already_seen=True)
        store = PostgresCycleStore("postgresql://test", lambda _: FakeConnection(cursor))
        result = store.record_ci_event(self.event())
        self.assertTrue(result["duplicate"])
        self.assertFalse(result["task_enqueued"])
        self.assertEqual(len(cursor.statements), 1)

    def test_rejects_missing_event_fields(self):
        store = PostgresCycleStore("postgresql://test", lambda _: FakeConnection(FakeCursor()))
        with self.assertRaises(ValueError):
            store.record_ci_event({"run_id": 1})


if __name__ == "__main__":
    unittest.main()
