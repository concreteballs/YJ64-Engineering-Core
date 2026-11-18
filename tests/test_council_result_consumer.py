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

    def __init__(self):
        self.checkpoints = []

    def load_latest_checkpoint(self):
        return self.checkpoints[-1] if self.checkpoints else None

    def save_checkpoint(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return True

    def record_council_resume_event(self, parent_task_id, request_id, artifact_ref, digest):
        self.resume_event = (parent_task_id, request_id, artifact_ref, digest)
        return {"accepted": True, "duplicate": False}


def make_task(status="completed"):
    from yj64_engineering_core.automation.browser_agent_bridge import create_envelope
    import json

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
    content = json.dumps(result).encode("utf-8")
    envelope = create_envelope(
        message_type="council_result",
        task_id=12,
        idempotency_key="council-result:req-1",
        payload={
            "request_id": "req-1",
            "session_id": "session-1",
            "correlation_id": "corr-1",
            "mode": "critique",
            "execution_status": status,
            "substantive_outcome": result["outcome"] if status == "completed" else None,
            "result_artifact_ref": "private://council/result-1" if status == "completed" else f"council-terminal://req-1/{status}",
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
            "result_artifact_ref": "private://council/result-1" if status == "completed" else f"council-terminal://req-1/{status}",
            "reason": None if status == "completed" else "council_timeout",
            "source": "yj64_native_council",
            "parent_task_id": 12,
            "browser_agent_envelope": envelope,
        },
    }, content


class CouncilResultConsumerTests(unittest.TestCase):
    def test_completed_result_is_validated_and_checkpointed(self):
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

    def test_incomplete_result_is_blocked_and_checkpointed(self):
        task, _ = make_task(status="blocked")
        context = FakeContext()
        decision = handle_council_result_ready(task, context)
        self.assertEqual(decision, TaskExecutionResult("completed"))
        self.assertEqual(context.checkpoints[0]["task_state"]["status"], "blocked")
        self.assertEqual(context.resume_event[1], "req-1")

    def test_invalid_semantic_shape_is_blocked(self):
        task, content = make_task()
        import json
        malformed = json.loads(content.decode("utf-8"))
        malformed["evidence"] = "not-a-list"
        context = FakeContext()
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(json.dumps(malformed).encode("utf-8")),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "invalid_council_result"))
        self.assertEqual(context.checkpoints, [])


if __name__ == "__main__":
    unittest.main()
