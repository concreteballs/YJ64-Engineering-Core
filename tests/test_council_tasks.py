import unittest

from yj64_engineering_core.automation.browser_agent_bridge import create_envelope
from yj64_engineering_core.automation.council_gateway import PROTOCOL_VERSION
from yj64_engineering_core.automation.council_tasks import (
    POLL_TASK,
    RESULT_READY_TASK,
    SUBMIT_TASK,
    enqueue_council_request_from_envelope,
    handle_poll_council_request,
    load_council_result_artifact,
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

    def suspend_for_council(self, checkpoint, request_id):
        self.suspended = (checkpoint, request_id)
        return True

    def record_council_resume_event(self, parent_task_id, request_id, artifact_ref, digest):
        self.resume_event = (parent_task_id, request_id, artifact_ref, digest)
        return {"accepted": True, "duplicate": False}


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
            "dissent": [{"participant_id": "P2", "reason": "insufficient test evidence"}],
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
        self.content = None

    def put(self, **kwargs):
        self.saved.append(kwargs)
        self.content = kwargs["content"]
        return "supabase-storage://yj64-private-artifacts/council/request-123/" + "a" * 64

    def get(self, _artifact_ref):
        return self.content


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
                "submitted_at": "2026-11-18T12:00:00Z",
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
                "submitted_at": "2026-11-18T12:00:00Z",
                "correlation_id": "task-12345678",
                "idempotency_key": "idem-key-12345678",
                "mode": "consensus",
                "poll_generation": 0,
                "max_poll_count": 20,
            },
        }

    def test_browser_agent_council_request_envelope_enters_existing_queue(self):
        store = FakeStore()
        envelope = create_envelope(
            message_type="council_request",
            task_id="engineering-task-123",
            idempotency_key="browser-agent-idem-12345",
            payload={
                "mode": "critique",
                "title": "Review a patch",
                "prompt": "Find defects in this proposed patch.",
                "context": {"repository": "concreteballs/YJ64-Engineering-Core"},
                "evidence_refs": ["https://github.com/concreteballs/YJ64-Engineering-Core"],
            },
        )
        result = enqueue_council_request_from_envelope(store, envelope)
        self.assertTrue(result["enqueued"])
        self.assertEqual(store.enqueued[0]["task_type"], SUBMIT_TASK)
        self.assertEqual(store.enqueued[0]["payload"]["parent_task_ref"], "engineering-task-123")
        self.assertEqual(store.enqueued[0]["payload"]["request"]["mode"], "critique")

    def test_parent_task_can_submit_and_suspend_for_council(self):
        from yj64_engineering_core.automation.council_tasks import handle_council_request_in_parent_task
        context = FakeContext()
        result = handle_council_request_in_parent_task(
            self.submit_task(), context, client_factory=lambda: FakeClient(),
        )
        self.assertEqual(result, TaskExecutionResult("suspended"))
        self.assertEqual(context.suspended[1], "request-123")
        self.assertEqual(context.suspended[0]["task_state"]["stage"], "waiting_council")
        self.assertEqual(context.store.enqueued[0]["task_type"], POLL_TASK)

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
        self.assertEqual(handoff["payload"]["browser_agent_envelope"]["message_type"], "council_result")
        loaded = load_council_result_artifact(
            handoff["payload"], artifact_store_factory=lambda: artifacts
        )
        self.assertEqual(loaded["request_id"], "request-123")
        self.assertEqual(loaded["outcome"], "unresolved_disagreement")
        self.assertEqual(len(artifacts.saved), 1)

    def test_result_handoff_envelope_is_stable_across_retries(self):
        context = FakeContext()
        artifacts = FakeArtifactStore()
        task = self.poll_task("completed")
        first = handle_poll_council_request(
            task, context,
            client_factory=lambda: FakeClient("completed"),
            artifact_store_factory=lambda: artifacts,
        )
        second = handle_poll_council_request(
            task, context,
            client_factory=lambda: FakeClient("completed"),
            artifact_store_factory=lambda: artifacts,
        )
        self.assertEqual(first, TaskExecutionResult("completed"))
        self.assertEqual(second, TaskExecutionResult("completed"))
        self.assertEqual(
            context.store.enqueued[0]["payload"],
            context.store.enqueued[1]["payload"],
        )

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
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(context.store.enqueued[0]["task_type"], RESULT_READY_TASK)
        self.assertEqual(context.store.enqueued[0]["payload"]["execution_status"], "blocked")
        self.assertEqual(context.store.enqueued[0]["payload"]["reason"], "council_session_id_mismatch")


if __name__ == "__main__":
    unittest.main()
