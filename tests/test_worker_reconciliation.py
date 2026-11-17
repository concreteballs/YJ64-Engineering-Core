import unittest

from yj64_engineering_core.automation.worker import (
    ProviderReconciliationDecision,
    TaskExecutionResult,
    WorkerRunner,
)


class FakeStore:
    def __init__(self, task=None, reconciliation_task=None, unknown=None):
        self.task = task
        self.reconciliation_task = reconciliation_task
        self.unknown = list(unknown or [])
        self.calls = []
        self.fail_state = "pending"
        self.lease_ok = True
        self.remaining = len(self.unknown)

    def run_recovery_maintenance(self, limit=100):
        self.calls.append(("recovery", limit))
        return {"quota_tasks_requeued": [], "unsent_reservations_expired": [], "deadline_tasks_failed": []}

    def claim_next_task(self, worker_id, lease_seconds=300):
        self.calls.append(("claim", worker_id, lease_seconds))
        return self.task

    def claim_next_reconciliation_task(self, worker_id, lease_seconds=300):
        self.calls.append(("claim_reconciliation", worker_id, lease_seconds))
        return self.reconciliation_task

    def list_unknown_provider_requests(self, task_id, worker_id, lease_seconds=300):
        self.calls.append(("list_unknown", task_id, worker_id, lease_seconds))
        return list(self.unknown)

    def list_recovered_provider_results(self, task_id, worker_id, lease_seconds=300):
        self.calls.append(("list_recovered", task_id, worker_id, lease_seconds))
        return [{"reservation_id": "already-done", "provider_result_ref": "artifact:result"}]

    def resolve_unknown_provider_request(self, task_id, worker_id, reservation_id, **kwargs):
        self.calls.append(("resolve", task_id, worker_id, reservation_id, kwargs))
        self.remaining -= 1
        return {
            "remaining_unknown_requests": self.remaining,
            "task_resumed": self.remaining == 0,
        }

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

    def test_reconciliation_uses_provider_evidence_and_never_completes_task(self):
        unknown = [{"reservation_id": "res-1", "idempotency_key": "key-1"}]
        store = FakeStore(reconciliation_task=self.task(), unknown=unknown)
        seen = {}

        def reconcile(task, requests, recovered, context):
            seen["requests"] = requests
            seen["recovered"] = recovered
            return [ProviderReconciliationDecision(
                reservation_id="res-1",
                outcome="provider_found",
                evidence_ref="evidence:lookup-1",
                provider_result_ref="artifact:provider-result-1",
            )]

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={},
            reconciliation_handler=reconcile,
        ).run_once()
        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["resolved_count"], 1)
        self.assertEqual(seen["requests"], unknown)
        self.assertTrue(any(call[0] == "resolve" for call in store.calls))
        self.assertFalse(any(call[0] in {"complete", "fail"} for call in store.calls))
        self.assertFalse(any(call[0] == "claim" for call in store.calls))

    def test_reconciliation_with_no_evidence_keeps_task_blocked(self):
        store = FakeStore(reconciliation_task=self.task(), unknown=[
            {"reservation_id": "res-1"}
        ])
        result = WorkerRunner(
            store, worker_id="worker-a", handlers={},
            reconciliation_handler=lambda task, unknown, recovered, context: [],
        ).run_once()
        self.assertEqual(result["status"], "reconciliation_pending")
        self.assertTrue(any(call[0] == "block" for call in store.calls))
        self.assertFalse(any(call[0] in {"resolve", "fail", "complete"} for call in store.calls))

    def test_reconciliation_rejects_unknown_or_duplicate_reservation_ids(self):
        store = FakeStore(reconciliation_task=self.task(), unknown=[
            {"reservation_id": "res-1"}
        ])
        result = WorkerRunner(
            store, worker_id="worker-a", handlers={},
            reconciliation_handler=lambda task, unknown, recovered, context: [
                ProviderReconciliationDecision("not-in-set", "provider_not_found", "evidence:1")
            ],
        ).run_once()
        self.assertEqual(result["status"], "reconciliation_pending")
        self.assertFalse(any(call[0] == "resolve" for call in store.calls))
        self.assertTrue(any(call[0] == "block" for call in store.calls))

    def test_reconciliation_handler_error_does_not_schedule_provider_retry(self):
        store = FakeStore(reconciliation_task=self.task(), unknown=[
            {"reservation_id": "res-1"}
        ])

        def broken(*args):
            raise RuntimeError("private provider response")

        result = WorkerRunner(
            store, worker_id="worker-a", handlers={},
            reconciliation_handler=broken,
        ).run_once()
        self.assertEqual(result["status"], "reconciliation_pending")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertFalse(any(call[0] in {"resolve", "fail", "complete"} for call in store.calls))

    def test_recovered_results_are_available_to_normal_task_handlers(self):
        store = FakeStore(self.task())
        observed = {}
        result = WorkerRunner(
            store, worker_id="worker-a",
            handlers={"demo": lambda task, context: (
                observed.setdefault("results", context.list_recovered_provider_results())
                and TaskExecutionResult("completed")
            )},
        ).run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(observed["results"][0]["provider_result_ref"], "artifact:result")


if __name__ == "__main__":
    unittest.main()
