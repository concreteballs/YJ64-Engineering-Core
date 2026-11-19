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
