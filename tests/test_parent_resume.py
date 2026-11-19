import hashlib
import json
import unittest

from yj64_engineering_core.automation.checkpoints import create_checkpoint
from yj64_engineering_core.automation.parent_resume import (
    PARENT_RESUME_PROTOCOL,
    build_parent_resume_checkpoint,
    fetch_child_result_artifact,
    validate_child_result,
    validate_parent_resume_checkpoint,
)


class FakeArtifactStore:
    def __init__(self, content):
        self.content = content
        self.requested = []

    def get(self, reference):
        self.requested.append(reference)
        return self.content


class ParentResumeTests(unittest.TestCase):
    def parent_checkpoint(self):
        return create_checkpoint(
            task_id="11", sequence=1, state="checkpointed",
            task_spec_version="engineering.v1",
            task_state={
                "stage": "waiting_child",
                "objective": "preserve parent objective",
                "expected_child_correlation_key": "cross-module:revision-7",
                "expected_child_protocol_version": PARENT_RESUME_PROTOCOL,
            },
            budgets={"tokens": 5000},
            approvals={"repository_write": False},
            artifact_refs=["private://candidate/rev-7"],
        )

    def child_result(self):
        return {
            "protocol_version": PARENT_RESUME_PROTOCOL,
            "parent_task_id": 11,
            "child_task_id": 22,
            "correlation_key": "cross-module:revision-7",
            "result_artifact_ref": "private://assessment/rev-7",
            "result_sha256": "a" * 64,
            "result_status": "completed",
            "result_is_untrusted_data": True,
        }

    def test_builds_resumed_checkpoint_and_preserves_parent_state(self):
        checkpoint = build_parent_resume_checkpoint(
            self.parent_checkpoint(), self.child_result(), resume_event_id=3,
        )
        resume = validate_parent_resume_checkpoint(checkpoint, parent_task_id=11)
        self.assertEqual(resume["child_task_id"], 22)
        self.assertEqual(resume["result_status"], "completed")
        self.assertEqual(resume["parent_task_state"]["objective"], "preserve parent objective")
        self.assertEqual(checkpoint["approvals"], {"repository_write": False})
        self.assertIn("private://assessment/rev-7", checkpoint["artifact_refs"])

    def test_rejects_wrong_parent(self):
        result = self.child_result()
        result["parent_task_id"] = 99
        with self.assertRaisesRegex(ValueError, "parent_identity"):
            build_parent_resume_checkpoint(self.parent_checkpoint(), result, resume_event_id=3)

    def test_rejects_wrong_correlation_key(self):
        result = self.child_result()
        result["correlation_key"] = "other-task"
        with self.assertRaisesRegex(ValueError, "does_not_match"):
            build_parent_resume_checkpoint(self.parent_checkpoint(), result, resume_event_id=3)

    def test_rejects_trust_escalation(self):
        result = self.child_result()
        result["result_is_untrusted_data"] = False
        with self.assertRaisesRegex(ValueError, "untrusted"):
            validate_child_result(result)

    def test_rejects_non_opaque_artifact_reference(self):
        result = self.child_result()
        result["result_artifact_ref"] += "?token=secret"
        with self.assertRaisesRegex(ValueError, "opaque"):
            validate_child_result(result)

    def test_rejects_unresolved_child_result_as_acceptance(self):
        result = self.child_result()
        result["result_status"] = "blocked"
        checkpoint = build_parent_resume_checkpoint(
            self.parent_checkpoint(), result, resume_event_id=3,
        )
        resume = validate_parent_resume_checkpoint(checkpoint, parent_task_id=11)
        self.assertEqual(resume["result_status"], "blocked")

    def test_fetches_and_verifies_child_artifact_digest(self):
        content = json.dumps({"schema_id": "example.result.v1", "data": "untrusted"}).encode()
        digest = hashlib.sha256(content).hexdigest()
        resume = {**self.child_result(), "result_sha256": digest}
        store = FakeArtifactStore(content)
        result = fetch_child_result_artifact(resume, store)
        self.assertEqual(result["data"], "untrusted")
        self.assertEqual(store.requested, [resume["result_artifact_ref"]])

    def test_rejects_child_artifact_digest_mismatch(self):
        store = FakeArtifactStore(b'{"result":"tampered"}')
        with self.assertRaisesRegex(ValueError, "sha256_mismatch"):
            fetch_child_result_artifact(self.child_result(), store)

    def test_rejects_non_json_child_artifact(self):
        content = b"not-json"
        resume = {**self.child_result(), "result_sha256": hashlib.sha256(content).hexdigest()}
        with self.assertRaisesRegex(ValueError, "valid_json"):
            fetch_child_result_artifact(resume, FakeArtifactStore(content))

    def test_does_not_fetch_non_completed_child_result(self):
        resume = {**self.child_result(), "result_status": "blocked"}
        with self.assertRaisesRegex(ValueError, "not_completed"):
            fetch_child_result_artifact(resume, FakeArtifactStore(b"{}"))


if __name__ == "__main__":
    unittest.main()
