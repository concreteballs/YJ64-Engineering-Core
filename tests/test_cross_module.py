import pytest
from yj64_engineering_core.cross_module import (
    ConditionDisposition, ConditionStatus, evaluate_condition_dispositions,
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
    return ConditionDisposition(
        candidate=CANDIDATE, reviewer_module="materials",
        condition_id="cond-" + str(len(text)), condition_text=text,
        status=status, rationale="Parent coordinator reviewed supporting record",
        decided_by="parent_coordinator", decision_version=3,
        evidence=({"evidence_id": "ev-1"},) if status is ConditionStatus.SATISFIED else (),
        **kwargs,
    )


def test_all_conditions_need_parent_disposition_and_evidence():
    ok, blockers = evaluate_condition_dispositions(CANDIDATE, [REVIEW], [
        disposition("validate fatigue life"),
        disposition("confirm interface tolerance"),
    ])
    assert ok and blockers == ()


def test_missing_condition_disposition_blocks():
    ok, blockers = evaluate_condition_dispositions(CANDIDATE, [REVIEW], [])
    assert not ok and len(blockers) == 2


def test_unresolved_deferred_and_rejected_dispositions_block():
    for status in (ConditionStatus.UNRESOLVED, ConditionStatus.DEFERRED, ConditionStatus.REJECTED):
        ok, blockers = evaluate_condition_dispositions(
            CANDIDATE, [REVIEW], [disposition("validate fatigue life", status)]
        )
        assert not ok and blockers


def test_satisfied_without_stable_evidence_is_rejected():
    with pytest.raises(ValueError, match="stable evidence"):
        disposition("validate fatigue life", evidence=())


def test_only_parent_coordinator_can_disposition():
    with pytest.raises(ValueError, match="only the parent coordinator"):
        ConditionDisposition(
            CANDIDATE, "materials", "c1", "condition", ConditionStatus.SATISFIED,
            "rationale", "materials", 1, ({"evidence_id": "ev-1"},),
        )


def test_wrong_candidate_revision_cannot_be_dispositioned():
    changed = dict(CANDIDATE, version=3)
    wrong = ConditionDisposition(
        changed, "materials", "c1", "validate fatigue life", ConditionStatus.SATISFIED,
        "rationale", "parent_coordinator", 4, ({"evidence_id": "ev-2"},),
    )
    with pytest.raises(ValueError, match="does not match"):
        evaluate_condition_dispositions(CANDIDATE, [REVIEW], [wrong])


def test_duplicate_disposition_is_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_condition_dispositions(
            CANDIDATE, [REVIEW],
            [disposition("validate fatigue life"), disposition("validate fatigue life")],
        )
