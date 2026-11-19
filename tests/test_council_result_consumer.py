import json
import unittest

from yj64_engineering_core.automation.council_gateway import PROTOCOL_VERSION
from yj64_engineering_core.automation.council_result_consumer import (
    handle_council_result_ready,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult


class FakeArtifactStore:
    def __init__(self, content):
        self.content = content

    def get(self, _ref):
        return self.content


class FakeContext:
    task_id = 71

    def __init__(self, resume_result=None):
        self.checkpoints = []
        self.resume_calls = []
        self.resume_result = resume_result or {"accepted": True, "duplicate": False}

    def load_latest_checkpoint(self):
        return self.checkpoints[-1] if self.checkpoints else None

    def save_checkpoint(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return True

    def record_council_resume_event(
        self, parent_task_id, request_id, artifact_ref, digest, resume_payload,
    ):
        self.resume_calls.append((
            parent_task_id, request_id, artifact_ref, digest, resume_payload,
        ))
        return self.resume_result


def make_task(
    status="completed", *, parent_task_id=12, parent_task_ref=None,
    envelope_task_id=None,
):
    from yj64_engineering_core.automation.browser_agent_bridge import create_envelope

    result = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "req-1",
        "session_id": "session-1",
        "status": "completed",
        "outcome": "unresolved_disagreement",
        "summary": "The council found insufficient evidence.",
        "claims": [{"claim": "A", "status": "unverified"}],
        "evidence": [],
        "dissent": [{"participant_id": "P2", "reason": "Need a test"}],
        "unresolved_questions": ["Run a physical test"],
        "assumptions": [],
        "limitations": [],
    }
    artifact_ref = (
        "private://council/result-1" if status == "completed"
        else f"council-terminal://req-1/{status}"
    )
    if envelope_task_id is None:
        envelope_task_id = (
            parent_task_id if parent_task_id is not None
            else parent_task_ref if parent_task_ref is not None
            else "req-1"
        )
    envelope = create_envelope(
        message_type="council_result",
        task_id=envelope_task_id,
        idempotency_key="council-result:req-1",
        payload={
            "request_id": "req-1",
            "session_id": "session-1",
            "correlation_id": "corr-1",
            "mode": "critique",
            "execution_status": status,
            "substantive_outcome": result["outcome"] if status == "completed" else None,
            "result_artifact_ref": artifact_ref,
            "reason": None if status == "completed" else "council_timeout",
            "source": "yj64_native_council",
        },
    )
    return {
        "task_id": 71,
        "payload": {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "req-1",
            "session_id": "session-1",
            "correlation_id": "corr-1",
            "mode": "critique",
            "execution_status": status,
            "result_artifact_ref": artifact_ref,
            "reason": None if status == "completed" else "council_timeout",
            "source": "yj64_native_council",
            "parent_task_id": parent_task_id,
            "parent_task_ref": parent_task_ref,
            "browser_agent_envelope": envelope,
        },
    }, json.dumps(result).encode("utf-8")


class CouncilResultConsumerTests(unittest.TestCase):
    def test_completed_result_is_validated_checkpointed_and_forwarded(self):
        task, content = make_task()
        context = FakeContext()
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("completed"))
        state = context.checkpoints[0]["task_state"]
        self.assertEqual(state["stage"], "council_result_verified")
        self.assertEqual(state["parent_task_id"], 12)
        self.assertEqual(state["council_result"]["outcome"], "unresolved_disagreement")
        self.assertTrue(state["model_output_is_untrusted_data"])
        self.assertEqual(context.resume_calls[0][0:3], (
            12, "req-1", "private://council/result-1",
        ))
        self.assertTrue(context.resume_calls[0][4]["model_output_is_untrusted_data"])
        self.assertEqual(
            context.resume_calls[0][4]["result"]["outcome"],
            "unresolved_disagreement",
        )

    def test_terminal_result_is_checkpointed_and_forwarded(self):
        task, _ = make_task(status="blocked")
        context = FakeContext()
        decision = handle_council_result_ready(task, context)
        self.assertEqual(decision, TaskExecutionResult("completed"))
        self.assertEqual(context.checkpoints[0]["task_state"]["status"], "blocked")
        self.assertEqual(context.resume_calls[0][4]["terminal"]["status"], "blocked")

    def test_invalid_semantic_shape_is_blocked_without_resume(self):
        task, content = make_task()
        malformed = json.loads(content.decode("utf-8"))
        malformed["evidence"] = "not-a-list"
        context = FakeContext()
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(json.dumps(malformed).encode("utf-8")),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "invalid_council_result"))
        self.assertEqual(context.checkpoints, [])
        self.assertEqual(context.resume_calls, [])

    def test_duplicate_delivery_reuses_checkpoint_and_resume_event(self):
        task, content = make_task()
        context = FakeContext()
        factory = lambda: FakeArtifactStore(content)
        first = handle_council_result_ready(task, context, artifact_store_factory=factory)
        second = handle_council_result_ready(task, context, artifact_store_factory=factory)
        self.assertEqual(first, TaskExecutionResult("completed"))
        self.assertEqual(second, TaskExecutionResult("completed"))
        self.assertEqual(len(context.checkpoints), 1)
        self.assertEqual(len(context.resume_calls), 2)
        self.assertEqual(context.resume_calls[0], context.resume_calls[1])

    def test_missing_parent_is_terminal_not_retried(self):
        task, content = make_task()
        context = FakeContext({"accepted": False, "reason": "parent_not_found"})
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "council_parent_not_resumable"))
        self.assertEqual(len(context.checkpoints), 1)

    def test_finished_parent_is_not_requeued(self):
        task, content = make_task()
        context = FakeContext({"accepted": False, "reason": "parent_not_waiting"})
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "council_parent_not_resumable"))

    def test_string_parent_reference_is_validated_but_not_mapped_to_queue_id(self):
        task, content = make_task(
            parent_task_id=None, parent_task_ref="engineering-task-123",
        )
        context = FakeContext()
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("completed"))
        self.assertEqual(context.resume_calls, [])
        self.assertEqual(context.checkpoints[0]["task_state"]["parent_task_ref"], "engineering-task-123")

    def test_envelope_cannot_be_rebound_to_another_parent(self):
        task, content = make_task(envelope_task_id=99)
        context = FakeContext()
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "invalid_council_result"))
        self.assertEqual(context.checkpoints, [])


if __name__ == "__main__":
    unittest.main()
