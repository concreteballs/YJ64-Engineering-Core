"""Conservative adapter from untrusted Council output to advisory decision records."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

from .decision_integrity import evaluate_decision_integrity
from .decision_records import create_claim_record, create_decision_record, create_evidence_record

_OUTCOMES = {
    "consensus": "supported",
    "qualified_consensus": "qualified",
    "unresolved_disagreement": "unresolved",
    "insufficient_evidence": "insufficient_evidence",
}
_CLAIMS = {"fact", "inference", "hypothesis", "test_result"}
_EVIDENCE = {
    "source": "document",
    "artifact": "document",
    "test": "deterministic_test",
    "simulation": "calculation",
    "measurement": "empirical_observation",
}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field}_must_be_object")
    result = dict(value)
    try:
        json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError(f"{field}_must_be_finite_json") from None
    return result


def _text(value: Any, field: str, limit: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
        raise ValueError(f"invalid_{field}")
    return value.strip()


def _list(value: Any, field: str, limit: int = 500, text_limit: int = 4000) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"invalid_{field}")
    return [_text(item, field, text_limit) for item in value]


def _objects(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 500:
        raise ValueError(f"invalid_{field}")
    return [_object(item, field + "_item") for item in value]


def _stable_id(prefix: str, request_id: str, external_id: str) -> str:
    digest = hashlib.sha256((request_id + ":" + external_id).encode()).hexdigest()[:32]
    return prefix + "-" + digest


def build_council_decision_assessment(resume: Mapping[str, Any]) -> dict[str, Any]:
    """Build an advisory-only bundle; never grant authority or verify model claims."""
    data = _object(resume, "council_resume")
    parent_id, request_id = data.get("parent_task_id"), data.get("request_id")
    session_id, digest = data.get("session_id"), data.get("result_sha256")
    if not isinstance(parent_id, int) or isinstance(parent_id, bool) or parent_id < 1:
        raise ValueError("invalid_parent_task_id")
    if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
        raise ValueError("invalid_council_request_id")
    if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
        raise ValueError("invalid_council_session_id")
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise ValueError("invalid_council_result_sha256")
    parent_state = data.get("parent_task_state")
    if (
        not isinstance(parent_state, Mapping)
        or parent_state.get("stage") != "council_resume_ready"
        or parent_state.get("expected_council_request_id") != request_id
    ):
        raise ValueError("council_parent_checkpoint_identity_mismatch")
    if data.get("execution_status") != "completed":
        raise ValueError("council_result_is_not_completed")
    if data.get("model_output_is_untrusted_data") is not True:
        raise ValueError("council_result_trust_marker_missing")

    result = _object(data.get("result"), "council_result")
    canonical_result = json.dumps(
        result, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if hashlib.sha256(canonical_result).hexdigest() != digest:
        raise ValueError("council_result_digest_mismatch")
    outcome = result.get("outcome")
    if outcome not in _OUTCOMES:
        raise ValueError("invalid_council_outcome")
    summary = _text(result.get("summary"), "council_summary", 12000)
    limitations = _list(result.get("limitations", []), "limitations", text_limit=2000)
    assumptions = _list(result.get("assumptions", []), "assumptions", text_limit=2000)
    unresolved = _list(result.get("unresolved_questions", []), "unresolved_questions")

    source_id = "council-" + hashlib.sha256(request_id.encode()).hexdigest()[:24]
    evidence_records, evidence_lookup = [], {}
    raw_evidence = _objects(result.get("evidence", []), "evidence")
    seen_ids, seen_refs = set(), set()
    for item in raw_evidence:
        external_id = _text(item.get("evidence_id"), "evidence_id", 128)
        reference = _text(item.get("reference"), "evidence_reference", 2048)
        description = _text(item.get("description"), "evidence_description", 12000)
        kind = item.get("evidence_type")
        if external_id in seen_ids or reference in seen_refs:
            raise ValueError("duplicate_council_evidence_identity")
        if kind not in _EVIDENCE:
            raise ValueError("unsupported_council_evidence_type")
        if "provenance" in item:
            _object(item["provenance"], "evidence_provenance")
        internal_id = _stable_id("e", request_id, external_id)
        for alias in (external_id, reference):
            if alias in evidence_lookup:
                raise ValueError("ambiguous_council_evidence_reference")
            evidence_lookup[alias] = internal_id
        seen_ids.add(external_id)
        seen_refs.add(reference)
        evidence_records.append(create_evidence_record(
            evidence_id=internal_id, kind=_EVIDENCE[kind], description=description,
            source_id=source_id, source_version=session_id, location=reference,
            content_hash=None, method=None, limitations=limitations,
            independently_verified=False,
        ))

    claim_records, relationships, seen_claims = [], [], set()
    for item in _objects(result.get("claims", []), "claims"):
        external_id = _text(item.get("claim_id"), "claim_id", 128)
        statement = _text(item.get("statement"), "claim_statement", 12000)
        reasoning = _text(item.get("reasoning"), "claim_reasoning", 12000, True)
        kind = item.get("epistemic_type")
        if external_id in seen_claims:
            raise ValueError("duplicate_council_claim_id")
        if kind not in _CLAIMS:
            raise ValueError("unsupported_council_claim_kind")
        seen_claims.add(external_id)
        scope = {
            "council_request_id": request_id, "council_session_id": session_id,
            "council_claim_id": external_id, "council_reasoning": reasoning,
        }
        confidence = item.get("confidence")
        if confidence is not None:
            if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                    or not 0 <= confidence <= 1 or not math.isfinite(confidence)):
                raise ValueError("invalid_council_claim_confidence")
            scope["council_confidence_claimed"] = confidence
        internal_id = _stable_id("c", request_id, external_id)
        claim_records.append(create_claim_record(
            claim_id=internal_id, statement=statement, kind=kind, source_id=source_id,
            status="unverified", scope=scope, limitations=limitations,
        ))
        refs = item.get("evidence_refs", [])
        if not isinstance(refs, list) or len(refs) > 500:
            raise ValueError("invalid_claim_evidence_refs")
        seen_refs_for_claim = set()
        for ref in refs:
            ref = _text(ref, "claim_evidence_ref", 2048)
            if ref in seen_refs_for_claim:
                raise ValueError("duplicate_claim_evidence_ref")
            seen_refs_for_claim.add(ref)
            linked_id = evidence_lookup.get(ref)
            if linked_id is None:
                raise ValueError("claim_references_unknown_council_evidence")
            relationships.append({
                "claim_id": internal_id, "evidence_id": linked_id,
                "relationship": "contextualizes",
            })

    dissent = []
    for item in _objects(result.get("dissent", []), "dissent"):
        participant = _text(item.get("participant_id"), "dissent_participant_id", 128)
        reason = _text(item.get("reason"), "dissent_reason", 3800)
        dissent.append(participant + ": " + reason)

    decision_id = "d-" + hashlib.sha256((request_id + ":" + digest).encode()).hexdigest()[:32]
    decision = create_decision_record(
        decision_id=decision_id, outcome=_OUTCOMES[outcome], summary=summary,
        claim_ids=[x["claim_id"] for x in claim_records],
        evidence_ids=[x["evidence_id"] for x in evidence_records],
        unresolved_questions=unresolved, dissent=dissent, assumptions=assumptions,
        limitations=limitations, requires_human_approval=True,
    )
    integrity = evaluate_decision_integrity(
        claims=claim_records, evidence=evidence_records, decision=decision,
        relationships=relationships,
    )

    voting = result.get("voting_summary")
    if voting is not None:
        voting = _object(voting, "voting_summary")
        forbidden = {"individual_votes", "ballots", "private_ratings", "competence_scores"}
        if forbidden.intersection(key.lower() for key in voting):
            raise ValueError("private_voting_details_are_not_exportable")
        counts = voting.get("aggregate_counts")
        if counts is not None:
            counts = _object(counts, "aggregate_counts")
            if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in counts.values()):
                raise ValueError("invalid_aggregate_vote_count")

    rounds = result.get("rounds_completed")
    if rounds is not None and (
        not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 0
    ):
        raise ValueError("invalid_council_rounds_completed")
    completion_reason = result.get("completion_reason")
    if completion_reason is not None:
        completion_reason = _text(completion_reason, "completion_reason", 512)

    return {
        "decision_bundle": {
            "claims": claim_records, "evidence": evidence_records,
            "decision": decision, "relationships": relationships,
        },
        "integrity_assessment": integrity,
        "supplemental": {
            "participant_positions": _objects(result.get("participant_positions", []), "participant_positions"),
            "tests_and_simulations": _objects(result.get("tests_and_simulations", []), "tests_and_simulations"),
            "voting_summary": voting, "rounds_completed": rounds,
            "completion_reason": completion_reason,
        },
        "source": {
            "parent_task_id": parent_id, "request_id": request_id,
            "session_id": session_id, "result_sha256": digest,
        },
        "model_output_is_untrusted_data": True,
        "authority": "advisory_only",
        "execution_allowed": False,
    }
