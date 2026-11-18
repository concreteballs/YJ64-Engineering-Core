import unittest

from yj64_engineering_core.automation.council_gateway import PROTOCOL_VERSION
from yj64_engineering_core.automation.council_tasks import (
    POLL_TASK,
    RESULT_READY_TASK,
    handle_poll_council_request,
    handle_submit_council_request,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult


class FakeStore:
    def __init__(self):
        self.enqueued = []

    def enqueue_task(self, task_type, payload, dedupe_key, *, max_attempts=3):
        self.enqueued.append({
            "task_type": task_type,
            "payload": payload,
            "dedupe_key": dedupe_key,
            "max_attempts": max_attempts,
        })
        return {
            "enqueued": True,
            "duplicate": False,
            "task_id": len(self.enqueued),
            "state": "pending",
        }


class FakeContext:
    task_id = 42
    worker_id = "test-worker"
    lease_seconds = 300

    def __init__(self):
        self.store = FakeStore()
        self.checkpoints = []

    def load_latest_checkpoint(self):
        return None

    def save_checkpoint(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return True


class FakeClient:
    def __init__(self, status="accepted"):
        self.status = status

    def submit(self, request):
        return {
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "accepted",
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
        }

    def get_status(self, request_id):
        return {
            "request_id": request_id,
            "session_id": "session-123",
            "status": self.status,
            "progress": {},
        }

    def get_result(self, request_id, session_id):
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": request_id,
            "session_id": session_id,
            "status": "completed",
            "outcome": "unresolved_disagreement",
            "summary": "The participants did not reach agreement.",
            "claims": [],
            "participant_positions": [],
            "dissent": [{"participant": "P2", "reason": "insufficient test evidence"}],
            "evidence": [],
            "unresolved_questions": ["Run an additional test."],
            "assumptions": [],
            "limitations": [],
            "rounds_completed": 3,
            "completion_reason": "round_limit_reached",
            "tests_and_simulations": [],
        }


class FakeArtifactStore:
    def __init__(self):
        self.saved = []

    def put(self, **kwargs):
        self.saved.append(kwargs)
        return "supabase-storage://yj64-private-artifacts/council/request-123/" + "a" * 64


class CouncilTaskTests(unittest.TestCase):
    def submit_task(self):
        return {
            "task_id": 42,
            "payload": {
                "protocol_version": PROTOCOL_VERSION,
                "request": {
                    "mode": "consensus",
                    "title": "Review",
                    "prompt": "Review the change.",
                    "correlation_id": "task-12345678",
                    "idempotency_key": "idem-key-12345678",
                    "context": {},
                    "evidence_refs": [],
                    "max_rounds": 3,
                    "timeout_seconds": 1800,
                    "max_output_tokens": 12000,
                },
                "parent_task_id": 9,
                "max_poll_count": 20,
            },
        }

    def poll_task(self, status):
        return {
            "task_id": 43,
            "payload": {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": "request-123",
                "session_id": "session-123",
                "parent_task_id": 9,
                "correlation_id": "task-12345678",
                "idempotency_key": "idem-key-12345678",
                "mode": "consensus",
                "poll_generation": 0,
                "max_poll_count": 20,
            },
        }

    def test_submit_persists_remote_ids_and_queues_poll_without_waiting(self):
        context = FakeContext()
        result = handle_submit_council_request(
            self.submit_task(), context,
            client_factory=lambda: FakeClient(),
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(context.checkpoints[0]["task_state"]["request_id"], "request-123")
        self.assertEqual(context.store.enqueued[0]["task_type"], POLL_TASK)
        self.assertEqual(context.store.enqueued[0]["dedupe_key"], "council-poll:request-123:0")

    def test_running_session_queues_next_poll_and_releases_worker(self):
        context = FakeContext()
        result = handle_poll_council_request(
            self.poll_task("running"), context,
            client_factory=lambda: FakeClient("running"),
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(context.store.enqueued[0]["task_type"], POLL_TASK)
        self.assertEqual(context.store.enqueued[0]["payload"]["poll_generation"], 1)

    def test_completed_session_persists_artifact_and_hands_off_result(self):
        context = FakeContext()
        artifacts = FakeArtifactStore()
        result = handle_poll_council_request(
            self.poll_task("completed"), context,
            client_factory=lambda: FakeClient("completed"),
            artifact_store_factory=lambda: artifacts,
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        handoff = context.store.enqueued[0]
        self.assertEqual(handoff["task_type"], RESULT_READY_TASK)
        self.assertEqual(handoff["payload"]["substantive_outcome"], "unresolved_disagreement")
        self.assertIn("supabase-storage://", handoff["payload"]["result_artifact_ref"])
        self.assertEqual(len(artifacts.saved), 1)

    def test_session_mismatch_is_blocked(self):
        class WrongSessionClient(FakeClient):
            def get_status(self, request_id):
                result = super().get_status(request_id)
                result["session_id"] = "different-session"
                return result

        context = FakeContext()
        result = handle_poll_council_request(
            self.poll_task("running"), context,
            client_factory=lambda: WrongSessionClient("running"),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "council_session_id_mismatch")
        self.assertEqual(context.store.enqueued, [])


if __name__ == "__main__":
    unittest.main()
