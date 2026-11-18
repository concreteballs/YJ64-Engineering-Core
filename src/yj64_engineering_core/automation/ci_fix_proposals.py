"""Build durable, human-reviewable repair plans from validated CI diagnoses.

This module never creates patches, executes commands, or modifies repositories.
Model-produced strings are treated as untrusted proposal content.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .worker import TaskExecutionResult


def build_ci_fix_proposal(analysis: dict, event: dict) -> dict:
    """Convert one validated analysis into a bounded repair plan, not a code patch."""
    if not isinstance(analysis, dict) or analysis.get("analysis_status") != "completed":
        raise ValueError("a completed CI analysis is required")
    report = analysis.get("analysis_json")
    if not isinstance(report, dict):
        raise ValueError("analysis_json must be an object")
    if not isinstance(event, dict) or event.get("event_id") != analysis.get("event_id"):
        raise ValueError("analysis event identity mismatch")

    confidence = report.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("analysis confidence is invalid")

    def bounded_list(name: str, limit: int = 12) -> list[str]:
        value = report.get(name)
        if not isinstance(value, list) or len(value) > limit:
            raise ValueError(f"{name} is invalid")
        if any(not isinstance(item, str) or len(item) > 1200 for item in value):
            raise ValueError(f"{name} contains invalid text")
        return [item.strip() for item in value if item.strip()]

    evidence = report.get("evidence")
    if not isinstance(evidence, list) or len(evidence) > 8:
        raise ValueError("analysis evidence is invalid")
    safe_evidence = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("analysis evidence item is invalid")
        excerpt = item.get("log_excerpt")
        interpretation = item.get("interpretation")
        if (
            not isinstance(excerpt, str) or len(excerpt) > 1200
            or not isinstance(interpretation, str) or len(interpretation) > 1200
        ):
            raise ValueError("analysis evidence text is invalid")
        safe_evidence.append({
            "log_excerpt": excerpt,
            "interpretation": interpretation,
        })

    classification = report.get("failure_classification")
    if classification not in {
        "dependency", "compiler", "test", "environment", "permissions",
        "network", "timeout", "configuration", "unknown",
    }:
        raise ValueError("analysis failure classification is invalid")

    status = "awaiting_review" if confidence >= 0.70 and classification != "unknown" else "needs_more_evidence"
    return {
        "schema_version": 1,
        "proposal_kind": "diagnostic_repair_plan",
        "proposal_status": status,
        "source": {
            "repository": event.get("repository"),
            "workflow": event.get("workflow"),
            "run_id": event.get("run_id"),
            "run_attempt": event.get("run_attempt"),
            "commit_sha": event.get("commit_sha"),
            "run_url": event.get("run_url"),
            "event_id": event.get("event_id"),
            "analysis_task_id": analysis.get("analysis_task_id"),
        },
        "diagnosis": {
            "summary": report.get("summary"),
            "failure_classification": classification,
            "root_cause": report.get("root_cause"),
            "confidence": confidence,
            "evidence": safe_evidence,
        },
        "proposed_actions": bounded_list("suggested_actions"),
        "verification_plan": bounded_list("verification_steps"),
        "risk_notes": bounded_list("risk_notes"),
        "implementation": {
            "status": "not_started",
            "patch_ready": False,
            "target_files": [],
            "diff": None,
            "repository_inspection_required": True,
            "human_approval_required": True,
            "auto_apply": False,
            "next_gate": (
                "inspect_exact_commit_and_prepare_reviewable_patch"
                if status == "awaiting_review"
                else "collect_more_evidence_before_patch"
            ),
        },
    }


def _enqueue_patch_generation(context, proposal_task_id: int, analysis_task_id: int) -> None:
    """Queue exact-commit inspection and review-only patch generation idempotently."""
    context.store.enqueue_task(
        "generate_ci_patch",
        {"proposal_task_id": proposal_task_id},
        f"ci-patch-generation:{analysis_task_id}",
        max_attempts=3,
    )


def process_ci_fix_proposal(task: dict, context, *, artifact_store) -> TaskExecutionResult:
    """Persist one repair-plan package for a completed CI analysis."""
    payload = task.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return TaskExecutionResult("blocked", "invalid_fix_proposal_payload")
    if not isinstance(payload, dict):
        return TaskExecutionResult("blocked", "invalid_fix_proposal_payload")
    analysis_task_id = payload.get("analysis_task_id")
    if not isinstance(analysis_task_id, int) or isinstance(analysis_task_id, bool) or analysis_task_id < 1:
        return TaskExecutionResult("blocked", "invalid_fix_proposal_payload")

    existing = context.store.get_ci_fix_proposal(context.task_id)
    if existing is not None:
        if existing.get("proposal_status") == "awaiting_review":
            _enqueue_patch_generation(context, context.task_id, existing["analysis_task_id"])
        return TaskExecutionResult("completed")

    analysis = context.store.get_ci_log_analysis(analysis_task_id)
    if analysis is None or analysis.get("analysis_status") != "completed":
        return TaskExecutionResult("blocked", "validated_analysis_unavailable")
    event = context.store.get_ci_event(analysis["event_id"])
    if event is None:
        return TaskExecutionResult("blocked", "analysis_source_event_missing")

    try:
        proposal = build_ci_fix_proposal(
            {**analysis, "analysis_task_id": analysis_task_id}, event
        )
    except (TypeError, ValueError):
        return TaskExecutionResult("blocked", "analysis_proposal_validation_failed")

    proposal_bytes = json.dumps(
        proposal, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(proposal_bytes).hexdigest()
    artifact_ref = artifact_store.put(
        namespace="ci-fix-proposals",
        content=proposal_bytes,
        content_type="application/json",
    )
    context.store.save_ci_fix_proposal(
        proposal_task_id=context.task_id,
        worker_id=context.worker_id,
        lease_seconds=context.lease_seconds,
        analysis_task_id=analysis_task_id,
        event_id=analysis["event_id"],
        proposal_status=proposal["proposal_status"],
        proposal_json=proposal,
        proposal_artifact_ref=artifact_ref,
        proposal_sha256=digest,
    )
    if proposal["proposal_status"] == "awaiting_review":
        _enqueue_patch_generation(context, context.task_id, analysis_task_id)
    return TaskExecutionResult("completed")
