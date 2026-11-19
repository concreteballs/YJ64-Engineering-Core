import unittest

from yj64_engineering_core.cross_module import (
    ConditionDisposition, ConditionStatus, evaluate_condition_dispositions,
    to_wire_condition_disposition,
)

CANDIDATE = {
    "schema_id": "yj64.cross_module.candidate.v1", "schema_version": "1.0",
    "candidate_id": "candidate-1", "version": 2, "candidate_schema_version": "1.0",
    "origin_module": "biology", "intended_scope": "", "input_refs": [], "provenance_refs": [],
}
REVIEW = {
    "candidate": CANDIDATE, "reviewer_module": "materials", "status": "conditional",
    "conditions": ["validate fatigue life", "confirm interface tolerance"],
}


def disposition(text, status=ConditionStatus.SATISFIED, **kwargs):
    evidence_refs = kwargs.pop("evidence", ({"evidence_id": "ev-1"},)
                               if status is ConditionStatus.SATISFIED else ())
    return ConditionDisposition(
        candidate=CANDIDATE, reviewer_module="materials",
        condition_id="cond-" + str(len(text)), condition_text=text,
        status=status, rationale="Parent coordinator reviewed supporting record",
        decided_by="parent_coordinator", decision_version=3,
        evidence=evidence_refs, **kwargs,
    )


class CrossModuleConditionDispositionTests(unittest.TestCase):
    def test_all_conditions_need_parent_disposition_and_evidence(self):
        ok, blockers = evaluate_condition_dispositions(CANDIDATE, [REVIEW], [
            disposition("validate fatigue life"), disposition("confirm interface tolerance"),
        ])
        self.assertTrue(ok)
        self.assertEqual(blockers, ())

    def test_missing_condition_disposition_blocks(self):
        ok, blockers = evaluate_condition_dispositions(CANDIDATE, [REVIEW], [])
        self.assertFalse(ok)
        self.assertEqual(len(blockers), 2)

    def test_unresolved_deferred_and_rejected_dispositions_block(self):
        for status in (ConditionStatus.UNRESOLVED, ConditionStatus.DEFERRED, ConditionStatus.REJECTED):
            with self.subTest(status=status):
                ok, blockers = evaluate_condition_dispositions(
                    CANDIDATE, [REVIEW], [disposition("validate fatigue life", status)]
                )
                self.assertFalse(ok)
                self.assertTrue(blockers)

    def test_satisfied_without_stable_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "stable evidence"):
            disposition("validate fatigue life", evidence=())

    def test_only_parent_coordinator_can_disposition(self):
        with self.assertRaisesRegex(ValueError, "only the parent coordinator"):
            ConditionDisposition(
                CANDIDATE, "materials", "c1", "condition", ConditionStatus.SATISFIED,
                "rationale", "materials", 1, ({"evidence_id": "ev-1"},),
            )

    def test_wrong_candidate_revision_cannot_be_dispositioned(self):
        changed = dict(CANDIDATE, version=3)
        wrong = ConditionDisposition(
            changed, "materials", "c1", "validate fatigue life", ConditionStatus.SATISFIED,
            "rationale", "parent_coordinator", 4, ({"evidence_id": "ev-2"},),
        )
        ok, blockers = evaluate_condition_dispositions(CANDIDATE, [REVIEW], [wrong])
        self.assertFalse(ok)
        self.assertTrue(blockers)

    def test_duplicate_disposition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_condition_dispositions(
                CANDIDATE, [REVIEW],
                [disposition("validate fatigue life"), disposition("validate fatigue life")],
            )

    def test_parent_disposition_serializes_to_canonical_schema(self):
        wire = to_wire_condition_disposition(disposition("validate fatigue life"))
        self.assertEqual(wire["schema_id"], "yj64.cross_module.condition_disposition.v1")
        self.assertEqual(wire["decided_by"], "parent_coordinator")
        self.assertEqual(wire["status"], "satisfied")
        self.assertEqual(wire["evidence"][0]["evidence_id"], "ev-1")


if __name__ == "__main__":
    unittest.main()


from yj64_engineering_core.cross_module import evaluate_cross_module_acceptance

PASS_REVIEW = {
    "candidate": CANDIDATE, "reviewer_module": "biology",
    "reviewer_version": "0.1.0", "status": "pass", "rationale": "Reviewed",
}
MATERIALS_REVIEW = {
    "candidate": CANDIDATE, "reviewer_module": "materials",
    "reviewer_version": "0.2.0", "status": "pass", "rationale": "Reviewed",
}
BIO_CONTRIBUTION = {
    "candidate": CANDIDATE, "module_id": "biology",
    "no_proposal": True, "rationale": "No evidence-backed improvement identified",
}
MATERIALS_CONTRIBUTION = {
    "candidate": CANDIDATE, "module_id": "materials",
    "no_proposal": True, "rationale": "No evidence-backed improvement identified",
}


class CrossModuleAcceptanceGateTests(unittest.TestCase):
    def test_acceptance_requires_complete_independent_reviews_and_contributions(self):
        result = evaluate_cross_module_acceptance(
            CANDIDATE, ["biology", "materials"],
            [PASS_REVIEW, MATERIALS_REVIEW],
            [BIO_CONTRIBUTION, MATERIALS_CONTRIBUTION],
        )
        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["blocking_findings"], [])

    def test_missing_contribution_blocks_acceptance(self):
        result = evaluate_cross_module_acceptance(
            CANDIDATE, ["biology", "materials"],
            [PASS_REVIEW, MATERIALS_REVIEW], [BIO_CONTRIBUTION],
        )
        self.assertEqual(result["decision"], "pending")
        self.assertEqual(result["missing_contributions"], ["materials"])

    def test_origin_module_cannot_self_certify(self):
        result = evaluate_cross_module_acceptance(
            CANDIDATE, ["biology"], [PASS_REVIEW], [BIO_CONTRIBUTION],
        )
        self.assertEqual(result["decision"], "pending")
        self.assertIn("no-independent-reviewer", result["blocking_findings"])

    def test_conditional_review_needs_parent_disposition(self):
        conditional = dict(MATERIALS_REVIEW, status="conditional",
                           conditions=["validate interface tolerance"])
        blocked = evaluate_cross_module_acceptance(
            CANDIDATE, ["biology", "materials"], [PASS_REVIEW, conditional],
            [BIO_CONTRIBUTION, MATERIALS_CONTRIBUTION],
        )
        self.assertEqual(blocked["decision"], "pending")
        disposition = ConditionDisposition(
            candidate=CANDIDATE, reviewer_module="materials", condition_id="c-tolerance",
            condition_text="validate interface tolerance", status=ConditionStatus.SATISFIED,
            rationale="Parent checked the validation evidence", decided_by="parent_coordinator",
            decision_version=1, evidence=({"evidence_id": "ev-tolerance"},),
        )
        accepted = evaluate_cross_module_acceptance(
            CANDIDATE, ["biology", "materials"], [PASS_REVIEW, conditional],
            [BIO_CONTRIBUTION, MATERIALS_CONTRIBUTION], (disposition,),
        )
        self.assertEqual(accepted["decision"], "accepted")
        self.assertEqual(len(accepted["condition_dispositions"]), 1)
