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
