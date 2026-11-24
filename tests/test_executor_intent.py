import hashlib
import json
import unittest

from yj64_engineering_core.automation.executor_intent import build_executor_intent


def make_policy(stage="collect_independent_evidence"):
    policy = {
        "schema_version": "yj64.council.decision-policy.v1",
        "source": {
            "parent_task_id": 42,
            "request_id": "request-42",
            "session_id": "session-42",
            "result_sha256": "a" * 64,
        },
        "input_digest_sha256": "b" * 64,
        "recommended_next_stage": stage,
        "claim_checks": [],
        "review_flags": {"independent_evidence_established": False},
        "rationale_codes": ["council_output_is_advisory_only"],
        "authority": "advisory_only",
        "execution_allowed": False,
        "requires_human_approval": True,
        "permission_changes": [],
        "executable_actions": [],
    }
    policy["policy_digest_sha256"] = hashlib.sha256(
        json.dumps(
            policy, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return policy


def make_approval(policy, *, task_id="42", operation="engineering.collect_evidence"):
    return {
        "approval_id": "approval-42",
        "issuer": "human-review-service",
        "approved_at": "2026-11-22T19:00:00Z",
        "task_id": task_id,
        "policy_digest_sha256": policy["policy_digest_sha256"],
        "operation": operation,
        "permission_snapshot_digest": "c" * 64,
        "scope": {"artifact_refs": ["private://engineering/42/evidence-1"], "domain": "engineering"},
        "signature": "opaque-authenticated-signature",
    }


class ExecutorIntentTests(unittest.TestCase):
    def test_verified_scoped_approval_builds_typed_non_command_intent(self):
        policy = make_policy()
        approval = make_approval(policy)
        result = build_executor_intent(
            decision_policy=policy,
            approval=approval,
            task_id="42",
            permission_snapshot_digest="c" * 64,
            verify_approval=lambda value: value["issuer"] == "human-review-service",
        )
        self.assertEqual(result["operation"], "engineering.collect_evidence")
        self.assertTrue(result["dispatch_allowed"])
        self.assertEqual(result["authority"], "externally_approved_typed_handler_intent")
        self.assertEqual(result["commands"], [])
        self.assertIsNone(result["shell"])
        self.assertIsNone(result["arbitrary_code"])

    def test_missing_or_failed_approval_verifier_fails_closed(self):
        policy = make_policy()
        approval = make_approval(policy)
        with self.assertRaisesRegex(ValueError, "not_verified"):
            build_executor_intent(
                decision_policy=policy, approval=approval, task_id="42",
                permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: False,
            )

    def test_approval_cannot_be_replayed_for_another_task(self):
        policy = make_policy()
        approval = make_approval(policy, task_id="99")
        with self.assertRaisesRegex(ValueError, "scope_mismatch"):
            build_executor_intent(
                decision_policy=policy, approval=approval, task_id="42",
                permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: True,
            )

    def test_approval_cannot_authorize_a_different_operation(self):
        policy = make_policy()
        approval = make_approval(policy, operation="engineering.repository_write")
        with self.assertRaisesRegex(ValueError, "scope_mismatch"):
            build_executor_intent(
                decision_policy=policy, approval=approval, task_id="42",
                permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: True,
            )

    def test_policy_cannot_self_grant_execution_or_mutate_permissions(self):
        for field, value in (
            ("execution_allowed", True),
            ("permission_changes", ["repository_write"]),
            ("executable_actions", ["run-command"]),
        ):
            policy = make_policy()
            policy[field] = value
            with self.assertRaisesRegex(ValueError, "authority_invalid"):
                build_executor_intent(
                    decision_policy=policy, approval=make_approval(policy),
                    task_id="42", permission_snapshot_digest="c" * 64,
                    verify_approval=lambda _: True,
                )

    def test_policy_digest_tampering_is_rejected(self):
        policy = make_policy()
        policy["recommended_next_stage"] = "human_review"
        with self.assertRaisesRegex(ValueError, "digest_invalid"):
            build_executor_intent(
                decision_policy=policy, approval=make_approval(policy),
                task_id="42", permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: True,
            )

    def test_untrusted_text_cannot_inject_an_operation_or_command(self):
        policy = make_policy()
        approval = make_approval(policy)
        approval["scope"] = {
            "domain": "engineering",
            "requested_command": "rm -rf /",
        }
        with self.assertRaisesRegex(ValueError, "scope_has_unscoped_fields"):
            build_executor_intent(
                decision_policy=policy, approval=approval, task_id="42",
                permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: True,
            )


    def test_approval_is_bound_to_the_exact_permission_snapshot(self):
        policy = make_policy()
        approval = make_approval(policy)
        with self.assertRaisesRegex(ValueError, "scope_mismatch"):
            build_executor_intent(
                decision_policy=policy, approval=approval, task_id="42",
                permission_snapshot_digest="d" * 64,
                verify_approval=lambda _: True,
            )

    def test_policy_parent_identity_must_match_dispatch_target(self):
        policy = make_policy()
        with self.assertRaisesRegex(ValueError, "parent_task_mismatch"):
            build_executor_intent(
                decision_policy=policy, approval=make_approval(policy),
                task_id="43", permission_snapshot_digest="c" * 64,
                verify_approval=lambda _: True,
            )


    def test_idempotency_key_survives_permission_snapshot_refresh(self):
        policy = make_policy()
        first_approval = make_approval(policy)
        second_approval = make_approval(policy)
        second_approval["permission_snapshot_digest"] = "d" * 64

        first = build_executor_intent(
            decision_policy=policy, approval=first_approval, task_id="42",
            permission_snapshot_digest="c" * 64,
            verify_approval=lambda _: True,
        )
        second = build_executor_intent(
            decision_policy=policy, approval=second_approval, task_id="42",
            permission_snapshot_digest="d" * 64,
            verify_approval=lambda _: True,
        )
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
