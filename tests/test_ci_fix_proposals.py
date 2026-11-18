import unittest
from hashlib import sha256

from yj64_engineering_core.automation.ci_fix_proposals import (
    build_ci_fix_proposal,
    process_ci_fix_proposal,
)


def report(confidence=0.91):
    return {
        "summary": "The Python test workflow failed.",
        "failure_classification": "test",
        "root_cause": "A test double has an outdated method signature.",
        "evidence": [{
            "log_excerpt": "TypeError: claim_next_task() takes 2 positional arguments but 3 were given",
            "interpretation": "The fake store does not match the production interface.",
        }],
        "confidence": confidence,
        "suggested_actions": ["Update the fake store method signature to match the protocol."],
        "verification_steps": ["Run the focused worker tests.", "Run the complete Python test suite."],
        "risk_notes": ["Do not change production queue semantics to accommodate an outdated test double."],
    }


def event():
    return {
        "event_id": 7,
        "repository": "concreteballs/YJ64-Engineering-Core",
        "workflow": "Python tests",
        "run_id": 123,
        "run_attempt": 1,
        "commit_sha": "a" * 40,
        "run_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/123",
    }


class FakeArtifacts:
    def __init__(self):
        self.items = {}

    def put(self, *, namespace, content, content_type):
        ref = f"memory-artifact://{namespace}/{sha256(content).hexdigest()}"
        self.items[ref] = content
        return ref


class FakeStore:
    def __init__(self):
        self.analysis = {
            "analysis_task_id": 41,
            "event_id": 7,
            "analysis_status": "completed",
            "analysis_json": report(),
        }
        self.proposal = None
        self.saved = None

    def get_ci_fix_proposal(self, proposal_task_id):
        return self.proposal

    def get_ci_log_analysis(self, analysis_task_id):
        return self.analysis if analysis_task_id == 41 else None

    def get_ci_event(self, event_id):
        return event() if event_id == 7 else None

    def save_ci_fix_proposal(self, **kwargs):
        self.saved = kwargs
        self.proposal = {
            "proposal_task_id": kwargs["proposal_task_id"],
            "analysis_task_id": kwargs["analysis_task_id"],
            "proposal_status": kwargs["proposal_status"],
            "proposal_json": kwargs["proposal_json"],
        }

    def enqueue_task(self, task_type, payload, dedupe_key, max_attempts=3):
        self.enqueued = (task_type, payload, dedupe_key, max_attempts)
        return {"enqueued": True, "duplicate": False, "task_id": 53, "state": "pending"}


class FakeContext:
    store = None
    task_id = 52
    worker_id = "proposal-test-worker"
    lease_seconds = 300

    def __init__(self, store):
        self.store = store


class CiFixProposalTests(unittest.TestCase):
    def test_high_confidence_diagnosis_creates_review_only_plan(self):
        proposal = build_ci_fix_proposal(
            {"analysis_task_id": 41, "event_id": 7, "analysis_status": "completed", "analysis_json": report()},
            event(),
        )
        self.assertEqual(proposal["proposal_status"], "awaiting_review")
        self.assertTrue(proposal["implementation"]["human_approval_required"])
        self.assertFalse(proposal["implementation"]["auto_apply"])
        self.assertFalse(proposal["implementation"]["patch_ready"])
        self.assertIsNone(proposal["implementation"]["diff"])
        self.assertEqual(proposal["implementation"]["target_files"], [])
        self.assertTrue(proposal["implementation"]["repository_inspection_required"])

    def test_low_confidence_or_unknown_classification_needs_more_evidence(self):
        low = report(confidence=0.45)
        proposal = build_ci_fix_proposal(
            {"analysis_task_id": 41, "event_id": 7, "analysis_status": "completed", "analysis_json": low},
            event(),
        )
        self.assertEqual(proposal["proposal_status"], "needs_more_evidence")
        unknown = report()
        unknown["failure_classification"] = "unknown"
        proposal = build_ci_fix_proposal(
            {"analysis_task_id": 41, "event_id": 7, "analysis_status": "completed", "analysis_json": unknown},
            event(),
        )
        self.assertEqual(proposal["proposal_status"], "needs_more_evidence")

    def test_worker_persists_hashed_proposal(self):
        store = FakeStore()
        context = FakeContext(store)
        result = process_ci_fix_proposal(
            {"task_id": 52, "payload": {"analysis_task_id": 41}},
            context,
            artifact_store=FakeArtifacts(),
        )
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(store.saved["proposal_status"], "awaiting_review")
        self.assertEqual(store.saved["analysis_task_id"], 41)
        self.assertEqual(len(store.saved["proposal_sha256"]), 64)
        self.assertFalse(store.saved["proposal_json"]["implementation"]["auto_apply"])
        self.assertEqual(store.enqueued[0], "generate_ci_patch")
        self.assertEqual(store.enqueued[1], {"proposal_task_id": 52})

    def test_worker_rejects_missing_analysis(self):
        store = FakeStore()
        context = FakeContext(store)
        result = process_ci_fix_proposal(
            {"task_id": 52, "payload": {"analysis_task_id": 999}},
            context,
            artifact_store=FakeArtifacts(),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "validated_analysis_unavailable")

    def test_event_identity_must_match_analysis(self):
        with self.assertRaises(ValueError):
            build_ci_fix_proposal(
                {"analysis_task_id": 41, "event_id": 7, "analysis_status": "completed", "analysis_json": report()},
                {**event(), "event_id": 8},
            )


if __name__ == "__main__":
    unittest.main()
