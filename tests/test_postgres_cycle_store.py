import sys
import types
import unittest
from unittest.mock import patch

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

    def test_connect_disables_auto_prepare_for_transaction_pooler(self):
        calls = {}
        fake_connection = object()

        def fake_connect(database_url, **kwargs):
            calls["database_url"] = database_url
            calls.update(kwargs)
            return fake_connection

        fake_psycopg = types.SimpleNamespace(connect=fake_connect)
        with patch.dict(sys.modules, {"psycopg": fake_psycopg}):
            connection = PostgresCycleStore("postgresql://pooler")._connect()

        self.assertIs(connection, fake_connection)
        self.assertEqual(calls["database_url"], "postgresql://pooler")
        self.assertIsNone(calls["prepare_threshold"])

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
        cursor = FakeCursor(claim_row=(12, "process_ci_event", {"event_id": 73}, 1, 3, None))
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


    def test_save_checkpoint_is_idempotent_for_same_sequence_and_hash(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=1, state="running", task_spec_version="1",
            task_state={"stage": "design"}, budgets={"tokens": 1000},
            approvals={"physical_action": False},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class CheckpointCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id FROM yj64_task_queue" in query:
                    self._fetch = (42,)
                elif "INSERT INTO yj64_task_checkpoints" in query:
                    self._fetch = None
                elif "SELECT checkpoint_hash" in query:
                    self._fetch = (checkpoint["checkpoint_hash"],)

        cursor = CheckpointCursor()
        self.assertFalse(self.store(cursor).save_checkpoint(42, "worker-a", checkpoint))
        self.assertEqual(len(cursor.statements), 3)

    def test_save_checkpoint_rejects_conflicting_sequence(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=1, state="running", task_spec_version="1",
            task_state={"stage": "design"}, budgets={}, approvals={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class ConflictingCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id FROM yj64_task_queue" in query:
                    self._fetch = (42,)
                elif "INSERT INTO yj64_task_checkpoints" in query:
                    self._fetch = None
                elif "SELECT checkpoint_hash" in query:
                    self._fetch = ("f" * 64,)

        with self.assertRaisesRegex(ValueError, "different content"):
            self.store(ConflictingCursor()).save_checkpoint(42, "worker-a", checkpoint)

    def test_load_latest_checkpoint_verifies_integrity(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=2, state="checkpointed", task_spec_version="1",
            task_state={"stage": "review"}, budgets={}, approvals={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class LoadCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                self._fetch = (checkpoint,)

        loaded = self.store(LoadCursor()).load_latest_checkpoint(42)
        self.assertEqual(loaded, checkpoint)

    def test_load_latest_checkpoint_returns_none_when_missing(self):
        class EmptyCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                self._fetch = None

        self.assertIsNone(self.store(EmptyCursor()).load_latest_checkpoint(42))

    def test_checkpoint_store_rejects_invalid_queue_id(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).load_latest_checkpoint(True)


    def test_claim_returns_latest_verified_checkpoint_slot(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=3, state="checkpointed", task_spec_version="1",
            task_state={"stage": "resume"}, budgets={}, approvals={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        cursor = FakeCursor(
            claim_row=(12, "process_ci_event", {"event_id": 73}, 2, 3, checkpoint)
        )
        task = self.store(cursor).claim_next_task("worker-a")
        self.assertEqual(task["checkpoint"], checkpoint)

    def test_save_checkpoint_requires_current_live_lease(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=1, state="running", task_spec_version="1",
            task_state={}, budgets={}, approvals={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class NoLeaseCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                self._fetch = None

        with self.assertRaisesRegex(RuntimeError, "live task lease"):
            self.store(NoLeaseCursor()).save_checkpoint(42, "worker-a", checkpoint)


if __name__ == "__main__":
    unittest.main()
