import hashlib
import json
import unittest

from yj64_engineering_core.dispatcher import EngineeringDispatcher


def make_policy():
    policy = {
        "schema_version": "yj64.council.decision-policy.v1",
        "source": {
            "parent_task_id": 42,
            "request_id": "request-42",
            "session_id": "session-42",
            "result_sha256": "a" * 64,
        },
        "input_digest_sha256": "b" * 64,
        "recommended_next_stage": "collect_independent_evidence",
        "claim_checks": [],
        "review_flags": {},
        "rationale_codes": ["council_output_is_advisory_only"],
        "authority": "advisory_only",
        "execution_allowed": False,
        "requires_human_approval": True,
        "permission_changes": [],
        "executable_actions": [],
    }
    policy["policy_digest_sha256"] = hashlib.sha256(
        json.dumps(policy, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return policy


def make_approval(policy):
    return {
        "approval_id": "approval-42",
        "issuer": "trusted-review-service",
        "approved_at": "2026-11-23T09:00:00Z",
        "task_id": "42",
        "policy_digest_sha256": policy["policy_digest_sha256"],
        "permission_snapshot_digest": "c" * 64,
        "operation": "engineering.collect_evidence",
        "scope": {
            "domain": "engineering",
            "artifact_refs": ["private://engineering/42/evidence-1"],
        },
        "signature": "signed-approval",
    }


class ParentTaskContext:
    def __init__(self, task_id=42):
        self.task_id = task_id
        self.saved = []

    def load_latest_checkpoint(self):
        return None

    def save_checkpoint(self, checkpoint):
        self.saved.append(checkpoint)
        return True


class ApprovedDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EngineeringDispatcher()
        self.policy = make_policy()
        self.approval = make_approval(self.policy)
        self.context = ParentTaskContext()

    def dispatch(self, verifier=lambda _: True):
        return self.dispatcher.dispatch_approved_intent(
            decision_policy=self.policy,
            approval=self.approval,
            task_id="42",
            permission_snapshot_digest="c" * 64,
            verify_approval=verifier,
            execution_context=self.context,
        )

    def test_dispatches_only_after_external_approval_to_registered_handler(self):
        calls = []

        def handler(intent, context):
            calls.append((intent, context))
            return {"status": "accepted", "artifact_refs": intent["scope"]["artifact_refs"]}

        self.dispatcher.register_approved_intent_handler(
            "engineering.collect_evidence", handler,
        )
        result = self.dispatch()
        self.assertEqual(result.operation, "engineering.collect_evidence")
        self.assertEqual(result.intent["commands"], [])
        self.assertIsNone(result.intent["shell"])
        self.assertEqual(result.result["status"], "accepted")
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1], self.context)

    def test_invalid_approval_never_invokes_registered_handler(self):
        calls = []
        self.dispatcher.register_approved_intent_handler(
            "engineering.collect_evidence",
            lambda intent, context: calls.append(intent) or {"status": "bad"},
        )
        with self.assertRaisesRegex(ValueError, "not_verified"):
            self.dispatch(lambda _: False)
        self.assertEqual(calls, [])

    def test_missing_handler_fails_closed_after_approval(self):
        with self.assertRaisesRegex(LookupError, "no_approved_intent_handler"):
            self.dispatch()

    def test_context_must_belong_to_the_approved_parent_task(self):
        calls = []
        self.dispatcher.register_approved_intent_handler(
            "engineering.collect_evidence",
            lambda intent, context: calls.append(intent) or {"status": "bad"},
        )
        self.context = ParentTaskContext(task_id=99)
        with self.assertRaisesRegex(ValueError, "context_task_mismatch"):
            self.dispatch()
        self.assertEqual(calls, [])

    def test_only_fixed_operations_can_be_registered_and_duplicates_are_rejected(self):
        handler = lambda intent, context: {"status": "accepted"}
        with self.assertRaisesRegex(ValueError, "unsupported_approved_intent"):
            self.dispatcher.register_approved_intent_handler("engineering.run_shell", handler)
        self.dispatcher.register_approved_intent_handler("engineering.collect_evidence", handler)
        with self.assertRaisesRegex(ValueError, "already_registered"):
            self.dispatcher.register_approved_intent_handler("engineering.collect_evidence", handler)

    def test_handler_result_must_be_finite_json_object(self):
        self.dispatcher.register_approved_intent_handler(
            "engineering.collect_evidence",
            lambda intent, context: {"value": float("nan")},
        )
        with self.assertRaisesRegex(ValueError, "finite_json"):
            self.dispatch()

    def test_verifier_cannot_mutate_the_approval_after_validation(self):
        self.dispatcher.register_approved_intent_handler(
            "engineering.collect_evidence",
            lambda intent, context: {"status": "accepted"},
        )

        def mutating_verifier(approval):
            approval["operation"] = "engineering.run_shell"
            return True

        with self.assertRaisesRegex(ValueError, "verifier_mutated"):
            self.dispatch(mutating_verifier)


if __name__ == "__main__":
    unittest.main()
