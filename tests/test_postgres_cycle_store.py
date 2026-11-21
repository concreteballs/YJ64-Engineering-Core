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

    def fetchall(self):
        return []


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
        self.assertTrue(any("FOR UPDATE SKIP LOCKED" in query for query, _ in cursor.statements))
        self.assertEqual(task["attempts"], 1)

    def test_claim_validates_lease(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).claim_next_task("worker-a", lease_seconds=2)

    def test_renew_task_lease_requires_current_owner(self):
        cursor = FakeCursor(rowcount=1)
        self.assertTrue(self.store(cursor).renew_task_lease(12, "worker-a"))
        self.assertIn("lock_owner = %s", cursor.statements[0][0])
        self.assertIn("locked_at >=", cursor.statements[0][0])

    def test_renew_task_lease_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).renew_task_lease(12, "worker-a", 5)

    def test_complete_requires_current_lease_owner(self):
        cursor = FakeCursor(rowcount=1)
        self.assertTrue(self.store(cursor).complete_task(12, "worker-a"))
        self.assertIn("lock_owner = %s", cursor.statements[0][0])
        self.assertIn("NOT EXISTS", cursor.statements[0][0])
        self.assertIn("yj64_provider_request_reservations", cursor.statements[0][0])
        self.assertIn("deadline_at IS NULL OR deadline_at > now()", cursor.statements[0][0])

    def test_expire_deadline_tasks_skips_ambiguous_requests(self):
        cursor = FakeCursor()
        result = self.store(cursor).expire_deadline_tasks(limit=10)
        self.assertEqual(result, [])
        query = cursor.statements[0][0]
        self.assertIn("state IN ('pending', 'blocked', 'running')", query)
        self.assertIn("request_outcome_unknown", query)
        self.assertIn("NOT EXISTS", query)

    def test_defer_task_for_capacity_releases_lease_and_sets_retry_time(self):
        from datetime import datetime, timezone
        cursor = FakeCursor(rowcount=1)
        retry_at = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)
        result = self.store(cursor).defer_task_for_capacity(
            12, "worker-a", retry_at, "RPM window full"
        )
        self.assertTrue(result)
        query, params = cursor.statements[0]
        self.assertIn("available_at", query)
        self.assertIn("GREATEST(%s, now())", query)
        self.assertIn("lock_owner = NULL", query)
        self.assertIn("attempts = GREATEST(0, attempts - 1)", query)
        self.assertIn("capacity_deferrals = capacity_deferrals + 1", query)
        self.assertIn("max_capacity_deferrals", query)
        self.assertEqual(params[0], retry_at)

    def test_task_capacity_deferral_rejects_naive_datetime(self):
        from datetime import datetime
        with self.assertRaises(ValueError):
            self.store(FakeCursor()).defer_task_for_capacity(
                12, "worker-a", datetime(2026, 11, 17), "rate limit"
            )

    def test_recovery_maintenance_runs_both_bounded_recovery_operations(self):
        store = self.store(FakeCursor())
        with patch.object(PostgresCycleStore, "recover_due_quota_tasks", return_value=[12]) as quota, \
             patch.object(PostgresCycleStore, "expire_unsent_provider_reservations", return_value=["r1"]) as expired, \
             patch.object(PostgresCycleStore, "expire_deadline_tasks", return_value=[13]) as deadlines:
            result = store.run_recovery_maintenance(limit=25)
        quota.assert_called_once_with(limit=25)
        expired.assert_called_once_with(limit=25)
        deadlines.assert_called_once_with(limit=25)
        self.assertEqual(result, {
            "quota_tasks_requeued": [12],
            "unsent_reservations_expired": ["r1"],
            "deadline_tasks_failed": [13],
        })

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
        self.assertEqual(len(cursor.statements), 2)

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


    def test_save_checkpoint_requires_contiguous_sequence_and_previous_hash(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=2, state="running", task_spec_version="1",
            task_state={"stage": "next"}, budgets={}, approvals={},
            previous_checkpoint_hash="a" * 64,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class BrokenChainCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id FROM yj64_task_queue" in query:
                    self._fetch = (42,)
                elif "SELECT checkpoint_hash" in query:
                    self._fetch = None
                elif "SELECT sequence, checkpoint_hash" in query:
                    self._fetch = (1, "b" * 64)

        with self.assertRaisesRegex(ValueError, "previous hash"):
            self.store(BrokenChainCursor()).save_checkpoint(42, "worker-a", checkpoint)

    def test_save_first_checkpoint_persists_after_live_lease(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from datetime import datetime, timezone

        checkpoint = create_checkpoint(
            task_id="task-a", sequence=1, state="running", task_spec_version="1",
            task_state={"stage": "start"}, budgets={}, approvals={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        class InsertCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id FROM yj64_task_queue" in query:
                    self._fetch = (42,)
                elif "SELECT checkpoint_hash" in query or "SELECT sequence, checkpoint_hash" in query:
                    self._fetch = None
                elif "INSERT INTO yj64_task_checkpoints" in query:
                    self._fetch = (99,)

        cursor = InsertCursor()
        self.assertTrue(self.store(cursor).save_checkpoint(42, "worker-a", checkpoint))
        self.assertEqual(len(cursor.statements), 4)


    def test_council_resume_appends_parent_checkpoint_and_preserves_permissions(self):
        import json
        from yj64_engineering_core.automation.checkpoints import create_checkpoint, verify_checkpoint

        parent_checkpoint = create_checkpoint(
            task_id="9", sequence=4, state="checkpointed", task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_council",
                "expected_council_request_id": "req-9",
                "session_id": "session-9",
                "objective": "original objective",
                "decision_log": ["decision-1"],
            },
            budgets={"tokens": 5000},
            approvals={"repository_write": False, "deploy": False},
            artifact_refs=["private://source/input-1"],
        )
        result_payload = {
            "parent_task_id": 9, "parent_task_ref": None,
            "request_id": "req-9", "session_id": "session-9",
            "execution_status": "completed",
            "result_artifact_ref": "private://council/result-9",
        }

        class ResumeCursor(FakeCursor):
            def __init__(self):
                super().__init__()
                self.step = 0
                self.inserted_checkpoint = None
                self.rowcount = 1

            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id, payload FROM yj64_task_queue" in query:
                    self._fetch = (71, result_payload)
                elif "SELECT state FROM yj64_task_queue" in query:
                    self._fetch = ("waiting",)
                elif "SELECT result_task_id, result_artifact_ref, result_sha256" in query:
                    self._fetch = None
                elif "SELECT checkpoint FROM yj64_task_checkpoints" in query:
                    self._fetch = (parent_checkpoint,)
                elif "INSERT INTO yj64_task_resume_events" in query:
                    self._fetch = (101,)
                elif "INSERT INTO yj64_task_checkpoints" in query:
                    self.inserted_checkpoint = json.loads(params[-1])
                    self._fetch = None
                elif "UPDATE yj64_task_queue" in query:
                    self.rowcount = 1
                    self._fetch = None
                else:
                    self._fetch = None

        cursor = ResumeCursor()
        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Run a bounded test."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        result = self.store(cursor).record_council_resume_event(
            9, 71, "worker-a", "req-9", "private://council/result-9",
            "c" * 64, resume_payload,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["state"], "pending")
        resumed = cursor.inserted_checkpoint
        self.assertIsNotNone(resumed)
        self.assertTrue(verify_checkpoint(resumed))
        self.assertEqual(resumed["sequence"], 5)
        self.assertEqual(resumed["task_state"]["stage"], "council_resume_ready")
        self.assertEqual(resumed["task_state"]["objective"], "original objective")
        self.assertEqual(resumed["task_state"]["decision_log"], ["decision-1"])
        self.assertEqual(resumed["task_state"]["council_resume"]["result"]["outcome"], "qualified_consensus")
        self.assertEqual(resumed["task_state"]["council_resume"]["session_id"], "session-9")
        self.assertEqual(resumed["budgets"], {"tokens": 5000})
        self.assertEqual(resumed["approvals"], {
            "repository_write": False, "deploy": False,
        })
        self.assertEqual(resumed["artifact_refs"], [
            "private://source/input-1", "private://council/result-9",
        ])

    def test_duplicate_council_result_delivery_does_not_requeue_parent(self):
        result_ref = "private://council/result-9"
        result_digest = "c" * 64
        result_task_payload = {
            "parent_task_id": 9, "parent_task_ref": None,
            "request_id": "req-9", "session_id": "session-9",
            "execution_status": "completed",
            "result_artifact_ref": result_ref,
        }

        class DuplicateCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id, payload FROM yj64_task_queue" in query:
                    self._fetch = (71, result_task_payload)
                elif "SELECT state FROM yj64_task_queue" in query:
                    self._fetch = ("completed",)
                elif "FROM yj64_task_resume_events" in query:
                    self._fetch = (101, result_ref, result_digest)
                else:
                    self._fetch = None

        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Run a bounded test."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        cursor = DuplicateCursor()
        result = self.store(cursor).record_council_resume_event(
            9, 71, "worker-a", "req-9", result_ref, result_digest, resume_payload,
        )
        self.assertEqual(result, {
            "accepted": True, "duplicate": True,
            "parent_task_id": 9, "state": "completed",
        })
        sql = [query for query, _ in cursor.statements]
        self.assertEqual(len(sql), 3)
        self.assertFalse(any("INSERT INTO yj64_task_resume_events" in query for query in sql))
        self.assertFalse(any("INSERT INTO yj64_task_checkpoints" in query for query in sql))
        self.assertFalse(any("UPDATE yj64_task_queue" in query for query in sql))

    def test_conflicting_duplicate_council_result_delivery_is_rejected(self):
        result_ref = "private://council/result-9"
        result_task_payload = {
            "parent_task_id": 9, "parent_task_ref": None,
            "request_id": "req-9", "session_id": "session-9",
            "execution_status": "completed",
            "result_artifact_ref": result_ref,
        }

        class ConflictingDuplicateCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id, payload FROM yj64_task_queue" in query:
                    self._fetch = (71, result_task_payload)
                elif "SELECT state FROM yj64_task_queue" in query:
                    self._fetch = ("pending",)
                elif "FROM yj64_task_resume_events" in query:
                    self._fetch = (101, result_ref, "d" * 64)
                else:
                    self._fetch = None

        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Run a bounded test."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        cursor = ConflictingDuplicateCursor()
        with self.assertRaisesRegex(ValueError, "conflicts with an existing event"):
            self.store(cursor).record_council_resume_event(
                9, 71, "worker-a", "req-9", result_ref, "c" * 64, resume_payload,
            )
        self.assertFalse(any(
            "INSERT INTO yj64_task_checkpoints" in query
            or "UPDATE yj64_task_queue" in query
            for query, _ in cursor.statements
        ))

    def test_council_resume_rejects_result_task_bound_to_another_parent(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        class WrongParentCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                self._fetch = (71, {
                    "parent_task_id": 10, "parent_task_ref": None,
                    "request_id": "req-9", "session_id": "session-9",
                    "execution_status": "completed",
                    "result_artifact_ref": "private://council/result-9",
                })

        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "consensus", "summary": "Review."},
            "model_output_is_untrusted_data": True,
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store(WrongParentCursor()).record_council_resume_event(
                9, 71, "worker-a", "req-9", "private://council/result-9",
                "c" * 64, resume_payload,
            )

    def test_council_resume_rejects_result_task_from_another_session(self):
        class WrongSessionCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                self._fetch = (71, {
                    "parent_task_id": 9, "parent_task_ref": None,
                    "request_id": "req-9", "session_id": "other-session",
                    "execution_status": "completed",
                    "result_artifact_ref": "private://council/result-9",
                })

        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "consensus", "summary": "Review."},
            "model_output_is_untrusted_data": True,
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store(WrongSessionCursor()).record_council_resume_event(
                9, 71, "worker-a", "req-9", "private://council/result-9",
                "c" * 64, resume_payload,
            )

    def test_council_resume_does_not_requeue_missing_or_finished_parent(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        result_payload = {
            "parent_task_id": 9, "parent_task_ref": None,
            "request_id": "req-9", "session_id": "session-9",
            "execution_status": "completed",
            "result_artifact_ref": "private://council/result-9",
        }

        class ParentStateCursor(FakeCursor):
            def __init__(self, parent_state):
                super().__init__()
                self.parent_state = parent_state
                self.calls = 0

            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id, payload FROM yj64_task_queue" in query:
                    self._fetch = (71, result_payload)
                elif "SELECT state FROM yj64_task_queue" in query:
                    self._fetch = (self.parent_state,) if self.parent_state is not None else None
                else:
                    self._fetch = None

        resume_payload = {
            "request_id": "req-9",
            "session_id": "session-9",
            "execution_status": "completed",
            "result": {"outcome": "consensus", "summary": "Review."},
            "model_output_is_untrusted_data": True,
        }
        missing = ParentStateCursor(None)
        missing_result = self.store(missing).record_council_resume_event(
            9, 71, "worker-a", "req-9", "private://council/result-9",
            "c" * 64, resume_payload,
        )
        self.assertEqual(missing_result["reason"], "parent_not_found")

        finished = ParentStateCursor("completed")
        finished_result = self.store(finished).record_council_resume_event(
            9, 71, "worker-a", "req-9", "private://council/result-9",
            "c" * 64, resume_payload,
        )
        self.assertEqual(finished_result["reason"], "parent_not_waiting")



    def test_suspend_task_for_child_persists_checkpoint_and_releases_lease(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint, verify_checkpoint

        checkpoint = create_checkpoint(
            task_id="42", sequence=5, state="checkpointed",
            task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_child",
                "expected_child_correlation_key": "cross-module:42:candidate-1:1",
                "expected_child_protocol_version": "yj64.parent-resume.v1",
            },
            budgets={"tokens": 1000}, approvals={"deploy": False},
            previous_checkpoint_hash="a" * 64,
        )

        class SuspendCursor(FakeCursor):
            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT task_id FROM yj64_task_queue" in query:
                    self._fetch = (42,)
                elif "SELECT sequence, checkpoint_hash" in query:
                    self._fetch = (4, "a" * 64)
                else:
                    self._fetch = None

        cursor = SuspendCursor()
        self.assertTrue(self.store(cursor).suspend_task_for_child(
            42, "worker-a", checkpoint,
            "cross-module:42:candidate-1:1", "yj64.parent-resume.v1",
        ))
        self.assertEqual(len(cursor.statements), 4)
        self.assertIn("INSERT INTO yj64_task_checkpoints", cursor.statements[2][0])
        self.assertIn("SET state = 'waiting'", cursor.statements[3][0])
        self.assertTrue(verify_checkpoint(checkpoint))

    def test_record_parent_resume_event_checkpoints_untrusted_result_and_requeues_parent(self):
        import json
        from yj64_engineering_core.automation.checkpoints import create_checkpoint, verify_checkpoint

        parent_checkpoint = create_checkpoint(
            task_id="9", sequence=4, state="checkpointed",
            task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_child",
                "expected_child_correlation_key": "cross-module:9:candidate-7:2",
                "expected_child_protocol_version": "yj64.parent-resume.v1",
                "objective": "preserve parent objective",
            },
            budgets={"tokens": 5000}, approvals={"repository_write": False},
            artifact_refs=["private://source/input"],
        )
        child_payload = {
            "parent_task_id": 9,
            "correlation_key": "cross-module:9:candidate-7:2",
            "parent_resume_protocol_version": "yj64.parent-resume.v1",
        }
        child_result = {
            "protocol_version": "yj64.parent-resume.v1",
            "parent_task_id": 9,
            "child_task_id": 71,
            "correlation_key": "cross-module:9:candidate-7:2",
            "result_artifact_ref": "private://cross-module/result",
            "result_sha256": "b" * 64,
            "result_status": "completed",
            "result_is_untrusted_data": True,
        }

        class ParentResumeCursor(FakeCursor):
            def __init__(self):
                super().__init__()
                self.inserted_checkpoint = None

            def execute(self, query, params):
                self.statements.append((query, params))
                if "SELECT payload FROM yj64_task_queue" in query:
                    self._fetch = (child_payload,)
                elif "SELECT state FROM yj64_task_queue" in query:
                    self._fetch = ("waiting",)
                elif "SELECT resume_event_id, child_task_id" in query:
                    self._fetch = None
                elif "SELECT checkpoint FROM yj64_task_checkpoints" in query:
                    self._fetch = (parent_checkpoint,)
                elif "INSERT INTO yj64_parent_task_resume_events" in query:
                    self._fetch = (101,)
                elif "INSERT INTO yj64_task_checkpoints" in query:
                    self.inserted_checkpoint = json.loads(params[-1])
                    self._fetch = None
                elif "UPDATE yj64_task_queue" in query:
                    self.rowcount = 1
                    self._fetch = None
                else:
                    self._fetch = None

        cursor = ParentResumeCursor()
        result = self.store(cursor).record_parent_resume_event(
            9, 71, "worker-child", child_result,
        )
        self.assertEqual(result, {
            "accepted": True, "duplicate": False,
            "resume_event_id": 101, "parent_task_id": 9, "state": "pending",
        })
        resumed = cursor.inserted_checkpoint
        self.assertTrue(verify_checkpoint(resumed))
        self.assertEqual(resumed["sequence"], 5)
        self.assertEqual(resumed["task_state"]["stage"], "parent_resume_ready")
        self.assertEqual(resumed["task_state"]["objective"], "preserve parent objective")
        self.assertTrue(resumed["task_state"]["child_resume"]["result_is_untrusted_data"])
        self.assertEqual(resumed["task_state"]["child_resume"]["resume_event_id"], 101)
        self.assertIn("SET state = 'pending'", cursor.statements[-1][0])

if __name__ == "__main__":
    unittest.main()
