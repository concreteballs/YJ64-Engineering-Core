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


class FakeResumeStore:
    def __init__(self):
        self.calls = []
        self.result = {"accepted": True, "duplicate": False}

    def record_council_resume_event(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeContext:
    task_id = 71
    worker_id = "result-worker"

    def __init__(self):
        self.checkpoints = []
        self.store = FakeResumeStore()

    def load_latest_checkpoint(self):
        return self.checkpoints[-1] if self.checkpoints else None

    def save_checkpoint(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return True


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
            "resume_request_id": "council-resume:abc",
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
        self.assertEqual(len(context.store.calls), 1)
        self.assertEqual(context.store.calls[0]["parent_task_id"], 12)
        self.assertEqual(context.store.calls[0]["result_task_id"], 71)
        self.assertEqual(context.store.calls[0]["council_request_id"], "council-resume:abc")
        self.assertEqual(context.store.calls[0]["result_sha256"], state["result_sha256"])
        self.assertEqual(len(state["result_sha256"]), 64)

    def test_parent_resume_rejection_blocks_after_preserving_result_checkpoint(self):
        task, content = make_task()
        context = FakeContext()
        context.store.result = {"accepted": False, "duplicate": False, "reason": "parent_not_waiting"}
        decision = handle_council_result_ready(
            task, context,
            artifact_store_factory=lambda: FakeArtifactStore(content),
        )
        self.assertEqual(decision, TaskExecutionResult("blocked", "parent_not_waiting"))
        self.assertEqual(len(context.checkpoints), 1)
        self.assertEqual(context.checkpoints[0]["task_state"]["stage"], "council_result_verified")

    def test_terminal_result_is_checkpointed_and_resumes_parent(self):
        task, _ = make_task(status="blocked")
        context = FakeContext()
        decision = handle_council_result_ready(task, context)
        self.assertEqual(decision, TaskExecutionResult("completed"))
        state = context.checkpoints[0]["task_state"]
        self.assertEqual(state["stage"], "council_result_terminal")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(len(context.store.calls), 1)
        self.assertEqual(context.store.calls[0]["council_request_id"], "council-resume:abc")
        self.assertEqual(
            context.store.calls[0]["result_artifact_ref"],
            "council-terminal://req-1/blocked",
        )

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
