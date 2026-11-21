import unittest

from yj64_engineering_core.automation.worker import (
    TaskExecutionResult,
    WorkerRunner,
)


class FakeStore:
    def __init__(self, task=None):
        self.task = task
        self.checkpoint = None
        self.calls = []
        self.fail_state = "pending"
        self.lease_ok = True

    def run_recovery_maintenance(self, limit=100):
        self.calls.append(("recovery", limit))
        return {"quota_tasks_requeued": [], "unsent_reservations_expired": [], "deadline_tasks_failed": []}

    def claim_next_task(self, worker_id, lease_seconds=300, task_types=None):
        self.calls.append(("claim", worker_id, lease_seconds, task_types))
        return self.task

    def renew_task_lease(self, task_id, worker_id, lease_seconds=300):
        self.calls.append(("renew", task_id, worker_id, lease_seconds))
        return self.lease_ok

    def save_checkpoint(self, queue_task_id, worker_id, checkpoint, lease_seconds=300):
        self.calls.append(("checkpoint", queue_task_id, worker_id, checkpoint, lease_seconds))
        self.checkpoint = checkpoint
        return True

    def load_latest_checkpoint(self, queue_task_id):
        self.calls.append(("load_checkpoint", queue_task_id))
        return self.checkpoint if self.checkpoint is not None else {"sequence": 1}

    def complete_task(self, task_id, worker_id):
        self.calls.append(("complete", task_id, worker_id))
        return self.lease_ok

    def fail_task(self, task_id, worker_id, error, retry_delay_seconds=60):
        self.calls.append(("fail", task_id, worker_id, error, retry_delay_seconds))
        return self.fail_state

    def block_task(self, task_id, worker_id, reason):
        self.calls.append(("block", task_id, worker_id, reason))
        return self.lease_ok

    def record_parent_resume_event(self, parent_task_id, child_task_id, worker_id, child_result):
        self.calls.append(("parent_resume", parent_task_id, child_task_id, worker_id, child_result))
        self.parent_resume_event = child_result
        return {"accepted": True, "duplicate": False}


class WorkerRunnerTests(unittest.TestCase):
    def task(self, task_type="demo"):
        return {"task_id": 7, "task_type": task_type, "payload": {"x": 1}, "checkpoint": None}

    def test_idle_run_performs_recovery_then_returns(self):
        store = FakeStore()
        result = WorkerRunner(store, worker_id="worker-a", handlers={}).run_once()
        self.assertEqual(result["status"], "idle")
        self.assertEqual([call[0] for call in store.calls], ["recovery", "claim"])

    def test_handler_can_renew_lease_and_save_checkpoint(self):
        store = FakeStore(self.task())
        observed = {}

        def handler(task, context):
            observed["task"] = task
            observed["renewed"] = context.renew_lease()
            observed["checkpoint"] = context.save_checkpoint({"sequence": 1})
            observed["loaded"] = context.load_latest_checkpoint()
            return TaskExecutionResult("completed")

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={"demo": handler}
        ).run_once()
        self.assertEqual(result["status"], "completed")
        self.assertTrue(observed["renewed"])
        self.assertTrue(observed["checkpoint"])
        self.assertEqual(observed["loaded"], {"sequence": 1})
        self.assertIn(("complete", 7, "worker-a"), store.calls)

    def test_resumed_parent_handler_loads_result_after_worker_restart_and_checkpoints_continuation(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        resume = {
            "request_id": "req-resume-1",
            "result_task_id": 71,
            "result_artifact_ref": "private://council/result-1",
            "result_sha256": "a" * 64,
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Test the proposed change."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        initial = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={
                "stage": "council_resume_ready",
                "objective": "preserve original task",
                "council_resume": resume,
            },
            budgets={"tokens": 1000}, approvals={"repository_write": False},
            artifact_refs=["private://source/evidence-1", "private://council/result-1"],
        )
        store = FakeStore(self.task())
        store.checkpoint = initial
        store.task["checkpoint"] = initial
        observed = {}

        def resumed_handler(task, context):
            observed["resume"] = context.load_council_resume()
            observed["checkpointed"] = context.checkpoint_council_resume_consumed({
                "next_stage": "engineering_continuation",
                "decision": "run_non_mutating_test",
            })
            return TaskExecutionResult("completed")

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={"demo": resumed_handler}
        ).run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(observed["resume"]["request_id"], "req-resume-1")
        self.assertTrue(observed["resume"]["model_output_is_untrusted_data"])
        self.assertTrue(observed["checkpointed"])
        self.assertEqual(store.checkpoint["task_state"]["stage"], "parent_resume_consumed")
        self.assertEqual(store.checkpoint["task_state"]["objective"], "preserve original task")
        self.assertEqual(
            store.checkpoint["task_state"]["parent_task_state"]["objective"],
            "preserve original task",
        )
        self.assertEqual(
            store.checkpoint["task_state"]["continuation"]["decision"],
            "run_non_mutating_test",
        )
        self.assertEqual(store.checkpoint["approvals"], {"repository_write": False})
        self.assertEqual(
            store.checkpoint["artifact_refs"],
            ["private://source/evidence-1", "private://council/result-1"],
        )

    def test_resumed_parent_cannot_suspend_without_checkpointing_continuation(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        resume = {
            "request_id": "req-resume-suspend",
            "result_task_id": 72,
            "result_artifact_ref": "private://council/result-suspend",
            "result_sha256": "f" * 64,
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Review the design."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        checkpoint = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={"stage": "council_resume_ready", "council_resume": resume},
            budgets={}, approvals={}, artifact_refs=["private://council/result-suspend"],
        )
        store = FakeStore(self.task())
        store.checkpoint = checkpoint
        store.task["checkpoint"] = checkpoint
        result = WorkerRunner(
            store,
            worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult("suspended")},
        ).run_once()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "council_resume_not_checkpointed")
        self.assertIn(
            ("block", 7, "worker-a", "council_resume_not_checkpointed"),
            store.calls,
        )
        self.assertNotIn(("complete", 7, "worker-a"), store.calls)

    def test_resumed_parent_cannot_complete_by_only_returning_completed(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        resume = {
            "request_id": "req-resume-2", "result_task_id": 71,
            "result_artifact_ref": "private://council/result-2",
            "result_sha256": "b" * 64, "execution_status": "completed",
            "result": {"outcome": "consensus", "summary": "Proceed with tests."},
            "terminal": None, "model_output_is_untrusted_data": True,
        }
        checkpoint = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={"stage": "council_resume_ready", "council_resume": resume},
            budgets={}, approvals={}, artifact_refs=["private://council/result-2"],
        )
        store = FakeStore(self.task())
        store.checkpoint = checkpoint
        store.task["checkpoint"] = checkpoint
        result = WorkerRunner(
            store, worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult("completed")},
        ).run_once()
        self.assertEqual(result["status"], "blocked")
        self.assertIn(("block", 7, "worker-a", "council_resume_not_checkpointed"), store.calls)
        self.assertNotIn(("complete", 7, "worker-a"), store.calls)

    def test_council_resume_cannot_escalate_approvals_or_discard_parent_context(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint

        resume = {
            "request_id": "req-resume-permissions",
            "result_task_id": 71,
            "result_artifact_ref": "private://council/result-permissions",
            "result_sha256": "e" * 64,
            "execution_status": "completed",
            "result": {"outcome": "qualified_consensus", "summary": "Review the proposal."},
            "terminal": None,
            "model_output_is_untrusted_data": True,
        }
        initial = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={
                "stage": "council_resume_ready",
                "objective": "original objective",
                "context": {"source": "original context"},
                "decisions": [{"id": "decision-1", "value": "retain"}],
                "history": [{"event": "created"}],
                "council_resume": resume,
            },
            budgets={"tokens": 1000},
            approvals={"repository_write": False},
            artifact_refs=["private://source/original", "private://council/result-permissions"],
        )
        store = FakeStore(self.task())
        store.checkpoint = initial
        store.task["checkpoint"] = initial

        def malicious_handler(task, context):
            context.load_council_resume()
            forged = create_checkpoint(
                task_id="7", sequence=2, state="checkpointed",
                task_spec_version="engineering.v1",
                task_state={
                    "stage": "parent_resume_consumed",
                    "parent_task_state": {
                        "stage": "council_resume_ready",
                        "objective": "changed objective",
                    },
                    "continuation": {"next_stage": "execute", "decision": "execute"},
                    "resume_kind": "council",
                    "resume_consumed": True,
                    "council_resume": resume,
                },
                budgets={"tokens": 1000},
                approvals={"repository_write": True},
                artifact_refs=["private://council/result-permissions"],
                previous_checkpoint_hash=initial["checkpoint_hash"],
            )
            context.save_checkpoint(forged)
            return TaskExecutionResult("completed")

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={"demo": malicious_handler},
        ).run_once()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(store.checkpoint, initial)
        self.assertEqual(store.checkpoint["approvals"], {"repository_write": False})
        self.assertNotIn(("complete", 7, "worker-a"), store.calls)

    def test_generic_parent_resume_requires_load_and_checkpoint_before_completion(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from yj64_engineering_core.automation.parent_resume import (
            PARENT_RESUME_PROTOCOL, build_parent_resume_checkpoint,
        )
        waiting = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_child",
                "expected_child_correlation_key": "parent:7:revision:2",
                "expected_child_protocol_version": PARENT_RESUME_PROTOCOL,
                "objective": "preserve parent objective",
                "context": {"origin": "parent"},
                "decisions": [{"id": "decision-1", "value": "retain"}],
                "history": [{"event": "parent-created"}],
            },
            budgets={"tokens": 1000},
            approvals={"repository_write": False},
            artifact_refs=["private://source/input"],
        )
        child_result = {
            "protocol_version": PARENT_RESUME_PROTOCOL,
            "parent_task_id": 7, "child_task_id": 71,
            "correlation_key": "parent:7:revision:2",
            "result_artifact_ref": "private://assessment/2",
            "result_sha256": "c" * 64, "result_status": "completed",
            "result_is_untrusted_data": True,
        }
        ready = build_parent_resume_checkpoint(waiting, child_result, resume_event_id=9)
        store = FakeStore(self.task())
        store.checkpoint = ready
        store.task["checkpoint"] = ready
        observed = {}

        def handler(task, context):
            observed["resume"] = context.load_parent_resume()
            self.assertTrue(context.checkpoint_parent_resume_consumed({
                "next_stage": "engineering_continuation",
                "decision": "continue",
            }))
            return TaskExecutionResult("completed")

        result = WorkerRunner(store, worker_id="worker-a", handlers={"demo": handler}).run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(observed["resume"]["child_task_id"], 71)
        self.assertEqual(store.checkpoint["task_state"]["stage"], "parent_resume_consumed")
        self.assertEqual(store.checkpoint["task_state"]["objective"], "preserve parent objective")
        self.assertEqual(store.checkpoint["task_state"]["context"], {"origin": "parent"})
        self.assertEqual(store.checkpoint["task_state"]["decisions"], [{"id": "decision-1", "value": "retain"}])
        self.assertEqual(store.checkpoint["task_state"]["history"], [{"event": "parent-created"}])
        self.assertEqual(
            store.checkpoint["task_state"]["parent_task_state"]["objective"],
            "preserve parent objective",
        )
        self.assertEqual(
            store.checkpoint["task_state"]["continuation"]["decision"],
            "continue",
        )
        self.assertEqual(store.checkpoint["approvals"], {"repository_write": False})
        self.assertEqual(
            store.checkpoint["artifact_refs"],
            ["private://source/input", "private://assessment/2"],
        )

    def test_generic_parent_resume_cannot_be_ignored(self):
        from yj64_engineering_core.automation.checkpoints import create_checkpoint
        from yj64_engineering_core.automation.parent_resume import (
            PARENT_RESUME_PROTOCOL, build_parent_resume_checkpoint,
        )
        waiting = create_checkpoint(
            task_id="7", sequence=1, state="checkpointed", task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_child",
                "expected_child_correlation_key": "parent:7:revision:3",
                "expected_child_protocol_version": PARENT_RESUME_PROTOCOL,
            }, budgets={}, approvals={},
        )
        ready = build_parent_resume_checkpoint(waiting, {
            "protocol_version": PARENT_RESUME_PROTOCOL,
            "parent_task_id": 7, "child_task_id": 72,
            "correlation_key": "parent:7:revision:3",
            "result_artifact_ref": "private://assessment/3",
            "result_sha256": "d" * 64, "result_status": "blocked",
            "result_is_untrusted_data": True,
        }, resume_event_id=10)
        store = FakeStore(self.task())
        store.checkpoint = ready
        store.task["checkpoint"] = ready
        result = WorkerRunner(
            store, worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult("completed")},
        ).run_once()
        self.assertEqual(result["status"], "blocked")
        self.assertIn(("block", 7, "worker-a", "parent_resume_not_consumed"), store.calls)

    def test_blocked_child_wakes_waiting_parent_with_untrusted_terminal_result(self):
        task = self.task()
        task["payload"] = {
            "parent_task_id": 19,
            "correlation_key": "parent:19:child:7",
            "parent_resume_protocol_version": "yj64.parent-resume.v1",
        }
        store = FakeStore(task)
        result = WorkerRunner(
            store, worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult("blocked", "review_rejected")},
        ).run_once()
        self.assertEqual(result["status"], "blocked")
        event = store.parent_resume_event
        self.assertEqual(event["result_status"], "blocked")
        self.assertEqual(event["result_summary"], "review_rejected")
        self.assertTrue(event["result_is_untrusted_data"])
        self.assertTrue(any(call[0] == "parent_resume" for call in store.calls))

    def test_unknown_task_type_is_blocked_not_discarded(self):
        store = FakeStore(self.task("unregistered"))
        result = WorkerRunner(store, worker_id="worker-a", handlers={}).run_once()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(call[0] == "block" for call in store.calls))

    def test_retry_decision_uses_bounded_scheduler(self):
        store = FakeStore(self.task())
        result = WorkerRunner(
            store,
            worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult(
                "retry", "provider_rate_limit", 90
            )},
        ).run_once()
        self.assertEqual(result["status"], "pending")
        self.assertIn(("fail", 7, "worker-a", "provider_rate_limit", 90), store.calls)

    def test_block_decision_releases_task(self):
        store = FakeStore(self.task())
        result = WorkerRunner(
            store,
            worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult(
                "blocked", "human_approval_required"
            )},
        ).run_once()
        self.assertEqual(result["status"], "blocked")

    def test_handler_exception_persists_only_exception_type(self):
        store = FakeStore(self.task())

        def handler(task, context):
            raise RuntimeError("contains a sensitive token value")

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={"demo": handler}
        ).run_once()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["error_type"], "RuntimeError")
        failure = next(call for call in store.calls if call[0] == "fail")
        self.assertEqual(failure[3], "handler_exception:RuntimeError")
        self.assertNotIn("sensitive", failure[3])

    def test_invalid_handler_result_is_safely_failed(self):
        store = FakeStore(self.task())
        result = WorkerRunner(
            store, worker_id="worker-a", handlers={"demo": lambda task, context: {"ok": True}}
        ).run_once()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["error_type"], "TypeError")

    def test_invalid_retry_delay_is_rejected(self):
        with self.assertRaises(ValueError):
            TaskExecutionResult("retry", "rate_limit", 86401)

    def test_worker_validates_lease_and_recovery_bounds(self):
        with self.assertRaises(ValueError):
            WorkerRunner(FakeStore(), worker_id="worker-a", handlers={}, lease_seconds=2)
        with self.assertRaises(ValueError):
            WorkerRunner(FakeStore(), worker_id="worker-a", handlers={}, recovery_limit=0)


if __name__ == "__main__":
    unittest.main()
