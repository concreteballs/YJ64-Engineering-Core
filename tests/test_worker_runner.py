import unittest

from yj64_engineering_core.automation.worker import (
    TaskExecutionResult,
    WorkerRunner,
)


class FakeStore:
    def __init__(self, task=None):
        self.task = task
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
        return True

    def load_latest_checkpoint(self, queue_task_id):
        self.calls.append(("load_checkpoint", queue_task_id))
        return {"sequence": 1}

    def complete_task(self, task_id, worker_id):
        self.calls.append(("complete", task_id, worker_id))
        return self.lease_ok

    def fail_task(self, task_id, worker_id, error, retry_delay_seconds=60):
        self.calls.append(("fail", task_id, worker_id, error, retry_delay_seconds))
        return self.fail_state

    def block_task(self, task_id, worker_id, reason):
        self.calls.append(("block", task_id, worker_id, reason))
        return self.lease_ok


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

    def test_unknown_task_type_is_blocked_not_discarded(self):
        store = FakeStore(self.task("unregistered"))
        result = WorkerRunner(store, worker_id="worker-a", handlers={}).run_once()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(call[0] == "block" for call in store.calls))

    def test_suspended_decision_does_not_complete_or_fail_released_parent(self):
        store = FakeStore(self.task())
        result = WorkerRunner(
            store,
            worker_id="worker-a",
            handlers={"demo": lambda task, context: TaskExecutionResult(
                "suspended", "waiting_for_council"
            )},
        ).run_once()
        self.assertEqual(result["status"], "waiting")
        self.assertFalse(any(call[0] in {"complete", "fail", "block"} for call in store.calls))

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
