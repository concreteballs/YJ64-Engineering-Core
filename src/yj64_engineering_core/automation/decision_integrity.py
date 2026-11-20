"""Deterministic, advisory assessment of claim/evidence relationships.

This module evaluates linkage and verification metadata only. It does not
establish physical truth, rank evidence kinds, alter claim statuses, or grant
execution authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .decision_records import SCHEMA_VERSION, validate_decision_bundle


def evaluate_decision_integrity(
    *,
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    relationships: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return a reproducible evidence-coverage assessment without changing claims."""
    bundle = validate_decision_bundle(
        claims=claims,
        evidence=evidence,
        decision=decision,
        relationships=relationships,
    )
    evidence_by_id = {item["evidence_id"]: item for item in bundle["evidence"]}
    relations_by_claim: dict[str, list[dict[str, str]]] = {
        item["claim_id"]: [] for item in bundle["claims"]
    }
    for relation in bundle["relationships"]:
        relations_by_claim[relation["claim_id"]].append(relation)

    assessed_claims = []
    findings = []
    statuses = []
    for claim in bundle["claims"]:
        claim_id = claim["claim_id"]
        linked = relations_by_claim[claim_id]
        grouped = {
            relation: sorted(
                row["evidence_id"] for row in linked
                if row["relationship"] == relation
            )
            for relation in ("supports", "refutes", "qualifies", "contextualizes")
        }
        support = grouped["supports"]
        refutes = grouped["refutes"]
        qualifies = grouped["qualifies"]
        contextualizes = grouped["contextualizes"]
        independently_verified_support = sorted(
            evidence_id for evidence_id in support
            if evidence_by_id[evidence_id]["independently_verified"]
        )
        independently_verified_refutations = sorted(
            evidence_id for evidence_id in refutes
            if evidence_by_id[evidence_id]["independently_verified"]
        )

        if support and refutes:
            assessment = "contested"
            findings.append(_finding(
                "conflicting_evidence_links", "warning", claim_id,
                evidence_ids=sorted(set(support + refutes)),
            ))
        elif refutes:
            assessment = "refuted_by_linked_evidence"
            findings.append(_finding(
                "refuting_evidence_linked", "warning", claim_id,
                evidence_ids=refutes,
            ))
        elif support and qualifies:
            assessment = "qualified_support"
        elif support and independently_verified_support:
            assessment = "supported_by_independent_evidence"
        elif support:
            assessment = "support_not_independently_verified"
            findings.append(_finding(
                "support_not_independently_verified", "warning", claim_id,
                evidence_ids=support,
            ))
        elif qualifies:
            assessment = "qualification_only"
        elif contextualizes:
            assessment = "context_only"
        else:
            assessment = "no_linked_evidence"
            findings.append(_finding("claim_has_no_linked_evidence", "warning", claim_id))

        provenance_gaps = []
        linked_ids = sorted(set(support + refutes + qualifies + contextualizes))
        for evidence_id in linked_ids:
            item = evidence_by_id[evidence_id]
            missing = [
                field for field in ("content_hash", "location", "method")
                if not item.get(field)
            ]
            if missing:
                provenance_gaps.append({"evidence_id": evidence_id, "missing_fields": missing})
                findings.append(_finding(
                    "evidence_provenance_incomplete", "info", claim_id,
                    evidence_ids=[evidence_id], missing_fields=missing,
                ))

        statuses.append(assessment)
        assessed_claims.append({
            "claim_id": claim_id,
            "declared_status": claim["status"],
            "assessment": assessment,
            "relationships": grouped,
            "independently_verified_support_ids": independently_verified_support,
            "independently_verified_refutation_ids": independently_verified_refutations,
            "provenance_gaps": provenance_gaps,
            "claim_limitations": list(claim["limitations"]),
            "linked_evidence_limitations": sorted({
                limitation
                for evidence_id in linked_ids
                for limitation in evidence_by_id[evidence_id]["limitations"]
            }),
        })

    if not statuses:
        overall = "insufficient_evidence"
    elif any(status in {"contested", "refuted_by_linked_evidence"} for status in statuses):
        overall = "contested"
    elif any(status in {
        "no_linked_evidence", "context_only", "support_not_independently_verified",
    } for status in statuses):
        overall = "insufficient_evidence"
    elif any(status in {"qualified_support", "qualification_only"} for status in statuses):
        overall = "qualified"
    elif all(status == "supported_by_independent_evidence" for status in statuses):
        overall = "supported"
    else:
        overall = "unresolved"

    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": bundle["decision"]["decision_id"],
        "declared_decision_outcome": bundle["decision"]["outcome"],
        "assessment": overall,
        "claims": assessed_claims,
        "findings": findings,
        "dissent": list(bundle["decision"]["dissent"]),
        "unresolved_questions": list(bundle["decision"]["unresolved_questions"]),
        "limitations": list(bundle["decision"]["limitations"]),
        "integrity": "records_hash_verified",
        "claim_statuses_mutated": False,
        "evidence_kind_used_as_truth_rank": False,
        "authority": "advisory_only",
    }


def _finding(
    code: str,
    severity: str,
    claim_id: str,
    *,
    evidence_ids: list[str] | None = None,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "claim_id": claim_id,
    }
    if evidence_ids is not None:
        finding["evidence_ids"] = evidence_ids
    if missing_fields is not None:
        finding["missing_fields"] = missing_fields
    return finding
