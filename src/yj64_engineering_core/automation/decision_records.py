"""Typed, provenance-preserving records for evidence-based engineering decisions.

This module validates data only. It never interprets model-authored text as
instructions, executes actions, or grants permissions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "yj64.decision-records.v1"
CLAIM_KINDS = {"fact", "inference", "hypothesis", "test_result"}
CLAIM_STATUSES = {"verified", "partially_verified", "hypothesis", "unverified", "refuted"}
EVIDENCE_KINDS = {
    "physical_experiment", "empirical_observation", "validated_model",
    "formal_proof", "deterministic_test", "calculation", "model_argument",
    "document", "source_code",
}
RELATIONSHIPS = {"supports", "refutes", "qualifies", "contextualizes"}
DECISION_OUTCOMES = {
    "supported", "qualified", "unresolved", "insufficient_evidence",
    "blocked", "rejected",
}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _json_object(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    result = dict(value)
    try:
        json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must contain finite JSON-compatible data") from None
    return result


def _required_text(value: Any, name: str, maximum: int = 12000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be non-empty text of at most {maximum} characters")
    return value.strip()


def _identifier(value: Any, name: str) -> str:
    text = _required_text(value, name, 128)
    if not _ID.fullmatch(text):
        raise ValueError(f"{name} has an invalid format")
    return text


def _unique_strings(values: Any, name: str) -> list[str]:
    if not isinstance(values, (list, tuple)) or isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a list of identifiers")
    result = [_identifier(item, name) for item in values]
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def create_claim_record(
    *, claim_id: str, statement: str, kind: str, source_id: str,
    status: str = "unverified", scope: Mapping[str, Any] | None = None,
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    """Create an attributed atomic claim; status is an assessment, not model authority."""
    if kind not in CLAIM_KINDS:
        raise ValueError("unsupported claim kind")
    if status not in CLAIM_STATUSES:
        raise ValueError("unsupported claim status")
    if isinstance(limitations, (str, bytes)) or not isinstance(limitations, (list, tuple)):
        raise ValueError("limitations must be a list of strings")
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "claim",
        "claim_id": _identifier(claim_id, "claim_id"),
        "statement": _required_text(statement, "statement"),
        "kind": kind,
        "source_id": _identifier(source_id, "source_id"),
        "status": status,
        "scope": _json_object(scope or {}, "scope"),
        "limitations": [_required_text(item, "limitation", 2000) for item in limitations],
    }
    return _seal(record)


def create_evidence_record(
    *, evidence_id: str, kind: str, description: str, source_id: str,
    source_version: str, content_hash: str | None = None,
    location: str | None = None, method: str | None = None,
    assumptions: Sequence[str] = (), limitations: Sequence[str] = (),
    independently_verified: bool = False,
) -> dict[str, Any]:
    """Create evidence with explicit provenance and applicability boundaries."""
    if kind not in EVIDENCE_KINDS:
        raise ValueError("unsupported evidence kind")
    if not isinstance(independently_verified, bool):
        raise ValueError("independently_verified must be boolean")
    if content_hash is not None and (
        not isinstance(content_hash, str) or not _SHA256.fullmatch(content_hash)
    ):
        raise ValueError("content_hash must be a lowercase SHA-256 hash")
    for name, values in (("assumptions", assumptions), ("limitations", limitations)):
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            raise ValueError(f"{name} must be a list of strings")
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "evidence",
        "evidence_id": _identifier(evidence_id, "evidence_id"),
        "kind": kind,
        "description": _required_text(description, "description"),
        "source_id": _identifier(source_id, "source_id"),
        "source_version": _required_text(source_version, "source_version", 512),
        "content_hash": content_hash,
        "location": _required_text(location, "location", 2048) if location is not None else None,
        "method": _required_text(method, "method", 2000) if method is not None else None,
        "assumptions": [_required_text(item, "assumption", 2000) for item in assumptions],
        "limitations": [_required_text(item, "limitation", 2000) for item in limitations],
        "independently_verified": independently_verified,
    }
    return _seal(record)


def create_decision_record(
    *, decision_id: str, outcome: str, summary: str,
    claim_ids: Sequence[str], evidence_ids: Sequence[str],
    unresolved_questions: Sequence[str] = (),
    dissent: Sequence[str] = (), assumptions: Sequence[str] = (),
    limitations: Sequence[str] = (), requires_human_approval: bool = False,
) -> dict[str, Any]:
    """Create a decision proposal. It contains no executable command or permission grant."""
    if outcome not in DECISION_OUTCOMES:
        raise ValueError("unsupported decision outcome")
    if not isinstance(requires_human_approval, bool):
        raise ValueError("requires_human_approval must be boolean")
    groups = {
        "unresolved_questions": unresolved_questions,
        "dissent": dissent,
        "assumptions": assumptions,
        "limitations": limitations,
    }
    text_groups = {}
    for name, values in groups.items():
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            raise ValueError(f"{name} must be a list of strings")
        text_groups[name] = [_required_text(item, name, 4000) for item in values]
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "decision",
        "decision_id": _identifier(decision_id, "decision_id"),
        "outcome": outcome,
        "summary": _required_text(summary, "summary"),
        "claim_ids": _unique_strings(claim_ids, "claim_ids"),
        "evidence_ids": _unique_strings(evidence_ids, "evidence_ids"),
        **text_groups,
        "requires_human_approval": requires_human_approval,
        "authority": "advisory_only",
    }
    return _seal(record)


def validate_decision_bundle(
    *, claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    relationships: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Validate references and preserve conflicts; never infer truth from consensus."""
    claim_map = _record_map(claims, "claim", "claim_id")
    evidence_map = _record_map(evidence, "evidence", "evidence_id")
    decision_data = _verify(decision, "decision")
    missing_claims = sorted(set(decision_data["claim_ids"]) - set(claim_map))
    missing_evidence = sorted(set(decision_data["evidence_ids"]) - set(evidence_map))
    if missing_claims or missing_evidence:
        raise ValueError("decision references missing claim or evidence records")

    normalized_relationships = []
    seen = set()
    for item in relationships:
        rel = _json_object(item, "relationship")
        claim_id = _identifier(rel.get("claim_id"), "claim_id")
        evidence_id = _identifier(rel.get("evidence_id"), "evidence_id")
        relationship = rel.get("relationship")
        if claim_id not in claim_map or evidence_id not in evidence_map:
            raise ValueError("relationship references an unknown claim or evidence record")
        if relationship not in RELATIONSHIPS:
            raise ValueError("unsupported evidence relationship")
        key = (claim_id, evidence_id, relationship)
        if key in seen:
            raise ValueError("duplicate evidence relationship")
        seen.add(key)
        normalized_relationships.append({
            "claim_id": claim_id, "evidence_id": evidence_id,
            "relationship": relationship,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "claims": [claim_map[key] for key in sorted(claim_map)],
        "evidence": [evidence_map[key] for key in sorted(evidence_map)],
        "decision": decision_data,
        "relationships": sorted(
            normalized_relationships,
            key=lambda row: (row["claim_id"], row["evidence_id"], row["relationship"]),
        ),
        "integrity": "records_hash_verified",
        "authority": "advisory_only",
    }


def verify_record(record: Mapping[str, Any]) -> bool:
    _verify(record, None)
    return True


def _record_map(records: Sequence[Mapping[str, Any]], expected_type: str, id_key: str) -> dict[str, dict[str, Any]]:
    if isinstance(records, (str, bytes)) or not isinstance(records, (list, tuple)):
        raise ValueError(f"{expected_type} records must be a list")
    result = {}
    for record in records:
        data = _verify(record, expected_type)
        identifier = _identifier(data.get(id_key), id_key)
        if identifier in result:
            raise ValueError(f"duplicate {expected_type} identifier")
        result[identifier] = data
    return result


def _seal(record: dict[str, Any]) -> dict[str, Any]:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    record["record_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return record


def _verify(record: Mapping[str, Any], expected_type: str | None) -> dict[str, Any]:
    data = _json_object(record, "record")
    supplied_hash = data.pop("record_hash", None)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported decision record schema")
    if expected_type is not None and data.get("record_type") != expected_type:
        raise ValueError("unexpected decision record type")
    if not isinstance(supplied_hash, str) or not _SHA256.fullmatch(supplied_hash):
        raise ValueError("record_hash must be a lowercase SHA-256 hash")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(supplied_hash, expected_hash):
        raise ValueError("decision record integrity check failed")
    data["record_hash"] = supplied_hash
    return data
