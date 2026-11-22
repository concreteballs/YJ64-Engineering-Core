"""Deterministic, non-executable guardrails for Council decision assessments.

This policy turns verified record structure into bounded review requirements.
It never interprets Council prose as commands, grants permissions, or authorizes
an executor. The engineering cycle remains responsible for domain validation.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .decision_integrity import evaluate_decision_integrity
from .decision_records import validate_decision_bundle

POLICY_SCHEMA_VERSION = "yj64.council.decision-policy.v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_KEYS = {
    "decision_bundle", "integrity_assessment", "supplemental", "source",
    "model_output_is_untrusted_data", "authority", "execution_allowed",
}
_BUNDLE_KEYS = {"claims", "evidence", "decision", "relationships"}


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("council_policy_input_must_be_finite_json") from None


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name}_must_be_object")
    result = dict(value)
    _canonical_json(result)
    return result


def _source_identity(value: Any) -> dict[str, Any]:
    source = _object(value, "council_policy_source")
    parent_id = source.get("parent_task_id")
    if not isinstance(parent_id, int) or isinstance(parent_id, bool) or parent_id < 1:
        raise ValueError("council_policy_parent_task_id_invalid")
    for key in ("request_id", "session_id"):
        item = source.get(key)
        if not isinstance(item, str) or not _ID.fullmatch(item):
            raise ValueError(f"council_policy_{key}_invalid")
    digest = source.get("result_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("council_policy_result_digest_invalid")
    if set(source) != {"parent_task_id", "request_id", "session_id", "result_sha256"}:
        raise ValueError("council_policy_source_has_unscoped_fields")
    return source


def _claim_check(claim: Mapping[str, Any]) -> dict[str, Any]:
    claim_id = claim.get("claim_id")
    status = claim.get("assessment")
    relationships = claim.get("relationships")
    if not isinstance(claim_id, str) or not _ID.fullmatch(claim_id):
        raise ValueError("council_policy_claim_id_invalid")
    if not isinstance(relationships, Mapping):
        raise ValueError("council_policy_claim_relationships_invalid")

    evidence_ids: set[str] = set()
    for relation in ("supports", "refutes", "qualifies", "contextualizes"):
        values = relationships.get(relation)
        if not isinstance(values, list):
            raise ValueError("council_policy_evidence_links_invalid")
        for value in values:
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError("council_policy_evidence_id_invalid")
            evidence_ids.add(value)

    checks = {
        "contested": ("resolve_conflict", "conflicting_evidence"),
        "refuted_by_linked_evidence": ("resolve_conflict", "refuting_evidence"),
        "no_linked_evidence": ("collect_independent_evidence", "claim_without_evidence"),
        "context_only": ("collect_independent_evidence", "context_is_not_support"),
        "support_not_independently_verified": (
            "collect_independent_evidence", "support_not_independently_verified",
        ),
        "support_with_independence_claim": (
            "authenticate_verification", "independence_claim_is_not_attestation",
        ),
        "qualified_support": ("verify_qualifications", "qualification_requires_validation"),
        "qualification_only": ("verify_qualifications", "qualification_only"),
    }
    if status not in checks:
        raise ValueError("council_policy_claim_assessment_unsupported")
    check, reason = checks[status]
    return {
        "claim_id": claim_id,
        "evidence_ids": sorted(evidence_ids),
        "check": check,
        "reason_code": reason,
    }


def evaluate_council_decision_policy(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute evidence integrity and return a bounded, advisory-only review plan.

    Model-authored summaries, claim statements, reasoning, evidence descriptions,
    dissent text and supplemental prose are deliberately excluded from the
    generated plan. Only validated record IDs and fixed policy enums are used.
    """
    data = _object(assessment, "council_decision_assessment")
    if set(data) != _TOP_LEVEL_KEYS:
        raise ValueError("council_decision_assessment_has_unscoped_fields")
    if (
        data.get("model_output_is_untrusted_data") is not True
        or data.get("authority") != "advisory_only"
        or data.get("execution_allowed") is not False
    ):
        raise ValueError("council_decision_assessment_authority_invalid")

    source = _source_identity(data.get("source"))
    raw_bundle = _object(data.get("decision_bundle"), "council_decision_bundle")
    if set(raw_bundle) != _BUNDLE_KEYS:
        raise ValueError("council_decision_bundle_has_unscoped_fields")
    bundle = validate_decision_bundle(
        claims=raw_bundle["claims"],
        evidence=raw_bundle["evidence"],
        decision=raw_bundle["decision"],
        relationships=raw_bundle["relationships"],
    )
    decision = bundle["decision"]
    if (
        decision.get("authority") != "advisory_only"
        or decision.get("requires_human_approval") is not True
    ):
        raise ValueError("council_decision_record_authority_invalid")
    if any(claim.get("status") != "unverified" for claim in bundle["claims"]):
        raise ValueError("council_claim_cannot_self_attest_verification")
    if any(evidence.get("independently_verified") is not False for evidence in bundle["evidence"]):
        raise ValueError("council_evidence_cannot_self_attest_independent_verification")

    recomputed_integrity = evaluate_decision_integrity(
        claims=bundle["claims"],
        evidence=bundle["evidence"],
        decision=decision,
        relationships=bundle["relationships"],
    )
    supplied_integrity = _object(data.get("integrity_assessment"), "council_integrity_assessment")
    if _canonical_json(supplied_integrity) != _canonical_json(recomputed_integrity):
        raise ValueError("council_integrity_assessment_does_not_match_records")

    supplemental = _object(data.get("supplemental"), "council_supplemental")
    if set(supplemental) != {
        "participant_positions", "tests_and_simulations", "voting_summary",
        "rounds_completed", "completion_reason",
    }:
        raise ValueError("council_supplemental_has_unscoped_fields")

    claim_checks = [
        _claim_check(item) for item in recomputed_integrity["claims"]
    ]
    decision_outcome = decision.get("outcome")
    if decision_outcome not in {
        "supported", "qualified", "unresolved", "insufficient_evidence",
        "blocked", "rejected",
    }:
        raise ValueError("council_decision_outcome_invalid")

    check_types = {item["check"] for item in claim_checks}
    has_conflict = (
        decision_outcome == "unresolved"
        or recomputed_integrity["assessment"] == "contested"
        or "resolve_conflict" in check_types
    )
    has_evidence_gap = (
        decision_outcome == "insufficient_evidence"
        or recomputed_integrity["assessment"] == "insufficient_evidence"
        or bool(decision["unresolved_questions"])
        or not claim_checks
        or bool(check_types.intersection({
            "collect_independent_evidence", "authenticate_verification",
            "verify_qualifications",
        }))
    )
    has_dissent = bool(decision["dissent"])

    if has_conflict:
        next_stage = "resolve_conflict"
        rationale = ["conflicting_or_unresolved_claims"]
    elif has_evidence_gap:
        next_stage = "collect_independent_evidence"
        rationale = ["independent_evidence_required"]
    elif decision_outcome in {"blocked", "rejected"} or has_dissent:
        next_stage = "human_review"
        rationale = ["human_review_required"]
    else:
        next_stage = "independent_domain_validation"
        rationale = ["domain_validation_required"]

    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "source": source,
        "input_digest_sha256": hashlib.sha256(_canonical_json(data)).hexdigest(),
        "recommended_next_stage": next_stage,
        "claim_checks": claim_checks,
        "review_flags": {
            "dissent_present": has_dissent,
            "unresolved_questions_present": bool(decision["unresolved_questions"]),
            "claims_present": bool(claim_checks),
            "independent_evidence_established": False,
        },
        "rationale_codes": ["council_output_is_advisory_only", *rationale],
        "authority": "advisory_only",
        "execution_allowed": False,
        "requires_human_approval": True,
        "permission_changes": [],
        "executable_actions": [],
    }
    policy["policy_digest_sha256"] = hashlib.sha256(_canonical_json(policy)).hexdigest()
    return policy
