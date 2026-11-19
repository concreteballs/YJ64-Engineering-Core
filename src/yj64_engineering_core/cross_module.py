"""Parent-owned, fail-closed condition disposition logic for cross-module reviews.

This module evaluates review conditions only. It does not mutate reviews,
accept candidates, route tasks, or grant execution permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class ConditionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    SATISFIED = "satisfied"
    REJECTED = "rejected"
    DEFERRED = "deferred"


def _candidate_key(value: Mapping[str, Any]) -> tuple[str, int, str, str]:
    try:
        key = (value["candidate_id"], value["version"],
               value["candidate_schema_version"], value["origin_module"])
    except (KeyError, TypeError) as exc:
        raise ValueError("candidate reference is incomplete") from exc
    if not isinstance(key[0], str) or not key[0].strip():
        raise ValueError("candidate_id is required")
    if type(key[1]) is not int or key[1] < 1:
        raise ValueError("candidate version must be a positive integer")
    if not isinstance(key[2], str) or not key[2].strip():
        raise ValueError("candidate_schema_version is required")
    if not isinstance(key[3], str) or not key[3].strip():
        raise ValueError("origin_module is required")
    return key


@dataclass(frozen=True)
class ConditionDisposition:
    candidate: Mapping[str, Any]
    reviewer_module: str
    condition_id: str
    condition_text: str
    status: ConditionStatus
    rationale: str
    decided_by: str
    decision_version: int
    evidence: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _candidate_key(self.candidate)
        for name in ("reviewer_module", "condition_id", "condition_text", "rationale"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.status, ConditionStatus):
            raise ValueError("status must be a ConditionStatus value")
        if self.decided_by != "parent_coordinator":
            raise ValueError("only the parent coordinator may disposition a review condition")
        if type(self.decision_version) is not int or self.decision_version < 1:
            raise ValueError("decision_version must be a positive integer")
        if self.status is ConditionStatus.SATISFIED:
            if not self.evidence or any(
                not isinstance(item, Mapping) or not str(item.get("evidence_id", "")).strip()
                for item in self.evidence
            ):
                raise ValueError("satisfied conditions require stable evidence references")


def evaluate_condition_dispositions(
    candidate: Mapping[str, Any],
    reviews: Iterable[Mapping[str, Any]],
    dispositions: Iterable[ConditionDisposition],
) -> tuple[bool, tuple[str, ...]]:
    """Return whether all CONDITIONAL findings are resolved, plus blockers.

    Every condition in every matching CONDITIONAL review needs exactly one
    disposition for the same candidate revision and reviewer. A disposition
    cannot alter the underlying review status. Non-satisfied states block.
    """
    target = _candidate_key(candidate)
    expected: dict[tuple[str, str], str] = {}
    blockers: list[str] = []

    for review in reviews:
        if not isinstance(review, Mapping):
            raise TypeError("reviews must contain mapping objects")
        ref = review.get("candidate")
        if not isinstance(ref, Mapping) or _candidate_key(ref) != target:
            continue
        if review.get("status") != "conditional":
            continue
        reviewer = review.get("reviewer_module")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("conditional review requires reviewer_module")
        conditions = review.get("conditions")
        if not isinstance(conditions, (list, tuple)) or not conditions:
            raise ValueError("conditional review must contain conditions")
        for condition in conditions:
            if not isinstance(condition, str) or not condition.strip():
                raise ValueError("condition text must be non-empty")
            expected[(reviewer, condition)] = condition

    seen: set[tuple[str, str]] = set()
    seen_ids: set[tuple[str, str]] = set()
    for item in dispositions:
        if not isinstance(item, ConditionDisposition):
            raise TypeError("dispositions must contain ConditionDisposition objects")
        if _candidate_key(item.candidate) != target:
            continue
        key = (item.reviewer_module, item.condition_text)
        if key not in expected:
            raise ValueError("disposition does not match a condition on this candidate revision")
        if key in seen:
            raise ValueError("duplicate disposition for the same review condition")
        id_key = (item.reviewer_module, item.condition_id)
        if id_key in seen_ids:
            raise ValueError("duplicate condition_id within a review")
        seen.add(key)
        seen_ids.add(id_key)
        if item.status is not ConditionStatus.SATISFIED:
            blockers.append(f"{item.reviewer_module}:{item.condition_id}:{item.status.value}")

    for reviewer, condition in expected:
        if (reviewer, condition) not in seen:
            blockers.append(f"{reviewer}:missing-disposition:{condition}")

    return (not blockers, tuple(sorted(blockers)))



def to_wire_condition_disposition(value: ConditionDisposition) -> dict[str, Any]:
    """Serialize a validated parent disposition using the shared wire schema."""
    if not isinstance(value, ConditionDisposition):
        raise TypeError("value must be ConditionDisposition")
    return {
        "schema_id": "yj64.cross_module.condition_disposition.v1",
        "schema_version": "1.0",
        "candidate": dict(value.candidate),
        "reviewer_module": value.reviewer_module,
        "condition_id": value.condition_id,
        "condition_text": value.condition_text,
        "status": value.status.value,
        "rationale": value.rationale,
        "evidence": [dict(item) for item in value.evidence],
        "decided_by": value.decided_by,
        "decision_version": value.decision_version,
    }


def evaluate_cross_module_acceptance(
    candidate: Mapping[str, Any],
    relevant_modules: Iterable[str],
    reviews: Iterable[Mapping[str, Any]],
    contributions: Iterable[Mapping[str, Any]],
    dispositions: Iterable[ConditionDisposition] = (),
) -> dict[str, Any]:
    """Build a fail-closed canonical assessment envelope.

    This is a pure parent-side gate. It does not execute tasks or grant
    permissions. All relevant modules must independently review and provide
    an enhancement contribution for the exact candidate revision.
    """
    target = _candidate_key(candidate)
    modules = tuple(sorted(set(relevant_modules)))
    if not modules or any(not isinstance(m, str) or not m.strip() for m in modules):
        raise ValueError("relevant_modules must contain non-empty module identifiers")
    if target[3] not in modules:
        raise ValueError("origin_module must be included in relevant_modules")

    review_list = tuple(reviews)
    contribution_list = tuple(contributions)
    disposition_list = tuple(dispositions)
    blockers: list[str] = []
    missing_reviews: list[str] = []
    missing_contributions: list[str] = []
    by_reviewer: dict[str, Mapping[str, Any]] = {}
    by_contributor: dict[str, Mapping[str, Any]] = {}

    for review in review_list:
        if not isinstance(review, Mapping):
            raise TypeError("reviews must contain mapping objects")
        ref = review.get("candidate")
        if not isinstance(ref, Mapping) or _candidate_key(ref) != target:
            continue
        reviewer = review.get("reviewer_module")
        if not isinstance(reviewer, str) or reviewer not in modules:
            blockers.append("review-from-unknown-or-invalid-module")
            continue
        if reviewer in by_reviewer:
            blockers.append(f"duplicate-review:{reviewer}")
            continue
        by_reviewer[reviewer] = review

    for contribution in contribution_list:
        if not isinstance(contribution, Mapping):
            raise TypeError("contributions must contain mapping objects")
        ref = contribution.get("candidate")
        if not isinstance(ref, Mapping) or _candidate_key(ref) != target:
            continue
        module = contribution.get("module_id")
        if not isinstance(module, str) or module not in modules:
            blockers.append("contribution-from-unknown-or-invalid-module")
            continue
        if module in by_contributor:
            blockers.append(f"duplicate-contribution:{module}")
            continue
        by_contributor[module] = contribution

    for module in modules:
        review = by_reviewer.get(module)
        if review is None:
            missing_reviews.append(module)
            continue
        status = review.get("status")
        if status == "reject":
            blockers.append(f"review-rejected:{module}")
        elif status == "not_reviewed":
            blockers.append(f"review-not-completed:{module}")
        elif status not in ("pass", "not_applicable", "conditional"):
            blockers.append(f"invalid-review-status:{module}")
        if status == "not_applicable" and not str(review.get("rationale", "")).strip():
            blockers.append(f"not-applicable-without-rationale:{module}")
        if review.get("hard_constraints"):
            blockers.append(f"hard-constraints:{module}")

        contribution = by_contributor.get(module)
        if contribution is None:
            missing_contributions.append(module)
        else:
            proposals = contribution.get("proposals", [])
            no_proposal = contribution.get("no_proposal", False)
            rationale = contribution.get("rationale", "")
            if no_proposal is True:
                if proposals or not isinstance(rationale, str) or not rationale.strip():
                    blockers.append(f"invalid-no-proposal-response:{module}")
            elif not isinstance(proposals, list) or not proposals:
                blockers.append(f"missing-enhancement-proposal-or-rationale:{module}")
            else:
                for proposal in proposals:
                    if not isinstance(proposal, Mapping):
                        blockers.append(f"invalid-proposal:{module}")
                        continue
                    pref = proposal.get("candidate")
                    if not isinstance(pref, Mapping) or _candidate_key(pref) != target:
                        blockers.append(f"proposal-candidate-mismatch:{module}")
                    if proposal.get("proposing_module") != module:
                        blockers.append(f"proposal-origin-mismatch:{module}")
                    if not proposal.get("evidence") or not proposal.get("success_criteria"):
                        blockers.append(f"proposal-evidence-or-criteria-missing:{module}")

    conditional_reviews = [
        r for r in by_reviewer.values() if r.get("status") == "conditional"
    ]
    conditions_ok, condition_blockers = evaluate_condition_dispositions(
        candidate, conditional_reviews, disposition_list
    )
    if not conditions_ok:
        blockers.extend(condition_blockers)

    if missing_reviews:
        blockers.extend(f"missing-review:{m}" for m in missing_reviews)
    if missing_contributions:
        blockers.extend(f"missing-contribution:{m}" for m in missing_contributions)

    independent_reviewers = {
        module for module, review in by_reviewer.items()
        if module != target[3] and review.get("status") in ("pass", "not_applicable", "conditional")
    }
    if not independent_reviewers:
        blockers.append("no-independent-reviewer")

    decision = "accepted" if not blockers else (
        "rejected" if any(x.startswith("review-rejected:") for x in blockers) else "pending"
    )
    return {
        "schema_id": "yj64.cross_module.assessment.v1",
        "schema_version": "1.0",
        "candidate": dict(candidate),
        "relevant_modules": list(modules),
        "reviews": list(review_list),
        "contributions": list(contribution_list),
        "missing_reviews": missing_reviews,
        "missing_contributions": missing_contributions,
        "blocking_findings": sorted(set(blockers)),
        "condition_dispositions": [to_wire_condition_disposition(x) for x in disposition_list],
        "decision": decision,
    }
