import unittest

from yj64_engineering_core.automation.decision_integrity import (
    evaluate_decision_integrity,
)
from yj64_engineering_core.automation.decision_records import (
    create_claim_record,
    create_decision_record,
    create_evidence_record,
)


class DecisionIntegrityTests(unittest.TestCase):
    def make_claim(self, status="unverified"):
        return create_claim_record(
            claim_id="claim-1",
            statement="The measured load is within the stated limit.",
            kind="test_result",
            source_id="test-run-1",
            status=status,
            limitations=["Only load case LC-1 is covered."],
        )

    def make_evidence(self, evidence_id="evidence-1", verified=False, kind="deterministic_test"):
        return create_evidence_record(
            evidence_id=evidence_id,
            kind=kind,
            description="Evidence record for load case LC-1.",
            source_id="ci-run-1",
            source_version="commit:abc123",
            content_hash="a" * 64,
            location="tests/test_load.py::test_limit",
            method="deterministic comparison",
            limitations=["Does not cover fatigue."],
            independently_verified=verified,
        )

    def make_decision(self, outcome="supported", evidence_ids=("evidence-1",)):
        return create_decision_record(
            decision_id="decision-1",
            outcome=outcome,
            summary="Advisory engineering assessment.",
            claim_ids=["claim-1"],
            evidence_ids=list(evidence_ids),
            dissent=["Boundary conditions need review."],
        )

    def test_independence_flag_is_not_an_authenticated_attestation(self):
        claim = self.make_claim()
        result = evaluate_decision_integrity(
            claims=[claim],
            evidence=[self.make_evidence(verified=True)],
            decision=self.make_decision(),
            relationships=[{
                "claim_id": "claim-1",
                "evidence_id": "evidence-1",
                "relationship": "supports",
            }],
        )
        self.assertEqual(result["assessment"], "insufficient_evidence")
        self.assertEqual(
            result["claims"][0]["assessment"],
            "support_with_independence_claim",
        )
        self.assertEqual(result["claims"][0]["declared_status"], "unverified")
        self.assertFalse(result["claim_statuses_mutated"])
        self.assertFalse(result["independent_verification_authenticated"])
        self.assertEqual(result["authority"], "advisory_only")
        self.assertEqual(result["dissent"], ["Boundary conditions need review."])

    def test_consensus_outcome_without_evidence_link_is_insufficient(self):
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[self.make_evidence(verified=True)],
            decision=self.make_decision("supported"),
        )
        self.assertEqual(result["assessment"], "insufficient_evidence")
        self.assertIn(
            "claim_has_no_linked_evidence",
            [finding["code"] for finding in result["findings"]],
        )

    def test_support_and_refutation_are_reported_as_contested(self):
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[
                self.make_evidence("evidence-1", verified=True),
                self.make_evidence("evidence-2", verified=True),
            ],
            decision=self.make_decision(
                "qualified", evidence_ids=("evidence-1", "evidence-2")
            ),
            relationships=[
                {"claim_id": "claim-1", "evidence_id": "evidence-1", "relationship": "supports"},
                {"claim_id": "claim-1", "evidence_id": "evidence-2", "relationship": "refutes"},
            ],
        )
        self.assertEqual(result["assessment"], "contested")
        self.assertEqual(result["claims"][0]["assessment"], "contested")

    def test_support_without_independent_verification_is_not_confirmed(self):
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[self.make_evidence(verified=False)],
            decision=self.make_decision(),
            relationships=[{
                "claim_id": "claim-1",
                "evidence_id": "evidence-1",
                "relationship": "supports",
            }],
        )
        self.assertEqual(result["assessment"], "insufficient_evidence")
        self.assertEqual(
            result["claims"][0]["assessment"],
            "support_not_independently_verified",
        )

    def test_evidence_kind_does_not_rank_truth(self):
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[self.make_evidence(verified=True, kind="model_argument")],
            decision=self.make_decision(),
            relationships=[{
                "claim_id": "claim-1",
                "evidence_id": "evidence-1",
                "relationship": "supports",
            }],
        )
        self.assertEqual(result["assessment"], "insufficient_evidence")
        self.assertEqual(
            result["claims"][0]["assessment"],
            "support_with_independence_claim",
        )
        self.assertFalse(result["evidence_kind_used_as_truth_rank"])
        self.assertFalse(result["independent_verification_authenticated"])

    def test_qualifying_evidence_yields_qualified_assessment(self):
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[self.make_evidence(verified=True)],
            decision=self.make_decision("qualified"),
            relationships=[{
                "claim_id": "claim-1",
                "evidence_id": "evidence-1",
                "relationship": "qualifies",
            }],
        )
        self.assertEqual(result["assessment"], "qualified")

    def test_incomplete_provenance_is_reported_not_hidden(self):
        evidence = create_evidence_record(
            evidence_id="evidence-1",
            kind="document",
            description="A document without pinpoint location.",
            source_id="doc-1",
            source_version="v1",
        )
        result = evaluate_decision_integrity(
            claims=[self.make_claim()],
            evidence=[evidence],
            decision=self.make_decision(),
            relationships=[{
                "claim_id": "claim-1",
                "evidence_id": "evidence-1",
                "relationship": "supports",
            }],
        )
        gaps = result["claims"][0]["provenance_gaps"]
        self.assertEqual(gaps[0]["missing_fields"], ["content_hash", "location", "method"])
        self.assertIn(
            "evidence_provenance_incomplete",
            [finding["code"] for finding in result["findings"]],
        )


if __name__ == "__main__":
    unittest.main()
