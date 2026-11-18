"""Consume and checkpoint verified Council Gateway results.

The consumer stores a normalized, evidence-linked result on its durable queue
checkpoint. It does not execute instructions contained in model output.
"""
from __future__ import annotations

from typing import Any, Callable
import hashlib
import json

from .checkpoints import create_checkpoint
from .council_gateway import PROTOCOL_VERSION
from .council_tasks import _payload, load_council_result_artifact
from .worker import TaskExecutionResult


_RESULT_LIST_FIELDS = (
    "claims",
    "evidence",
    "dissent",
    "unresolved_questions",
    "assumptions",
    "limitations",
)


def _validated_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate the structured result contract without trusting its prose."""
    outcome = result.get("outcome")
    summary = result.get("summary")
    if not isinstance(outcome, str) or not outcome.strip() or len(outcome) > 128:
        raise ValueError("invalid_council_result_outcome")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 20000:
        raise ValueError("invalid_council_result_summary")

    normalized: dict[str, Any] = {
        "outcome": outcome,
        "summary": summary,
    }
    for field in _RESULT_LIST_FIELDS:
        value = result.get(field, [])
        if not isinstance(value, list) or len(value) > 500:
            raise ValueError("invalid_council_result_" + field)
        normalized[field] = value
    # These optional fields are useful metadata, not executable instructions.
    for field in ("participant_positions", "tests_and_simulations"):
        value = result.get(field, [])
        if not isinstance(value, list) or len(value) > 500:
            raise ValueError("invalid_council_result_" + field)
        normalized[field] = value
    return normalized


def handle_council_result_ready(
    task: dict,
    context: Any,
    *,
    artifact_store_factory: Callable[[], Any] | None = None,
) -> TaskExecutionResult:
    """Verify a result artifact and persist its structured contents in a checkpoint."""
    try:
        payload = _payload(task)
        if payload.get("source") != "yj64_native_council":
            return TaskExecutionResult("blocked", "invalid_council_result_source")
        execution_status = payload.get("execution_status")
        if execution_status != "completed":
            reason = payload.get("reason")
            safe_reason = (
                reason if isinstance(reason, str)
                and reason.replace("_", "").replace("-", "").isalnum()
                and len(reason) <= 120 else "council_result_not_completed"
            )
            previous = context.load_latest_checkpoint()
            sequence = int(previous.get("sequence", 0)) + 1 if isinstance(previous, dict) else 1
            checkpoint = create_checkpoint(
                task_id=str(context.task_id),
                sequence=sequence,
                state="blocked",
                task_spec_version=PROTOCOL_VERSION,
                task_state={
                    "stage": "council_result_consumption",
                    "status": "blocked",
                    "reason": safe_reason,
                    "parent_task_id": payload.get("parent_task_id"),
                    "parent_task_ref": payload.get("parent_task_ref"),
                    "request_id": payload.get("request_id"),
                    "session_id": payload.get("session_id"),
                },
                budgets={},
                approvals={},
            )
            if not context.save_checkpoint(checkpoint):
                return TaskExecutionResult("retry", "council_result_checkpoint_failed", 90)
            return TaskExecutionResult("blocked", safe_reason)

        artifact_factory = artifact_store_factory
        result = load_council_result_artifact(
            payload, artifact_store_factory=artifact_factory
        )
        normalized = _validated_result(result)
    canonical_artifact = json.dumps(
        result, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    result_sha256 = hashlib.sha256(canonical_artifact).hexdigest()
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_result")
    except (OSError, RuntimeError):
        return TaskExecutionResult("retry", "council_result_artifact_unavailable", 90)

    artifact_ref = payload.get("result_artifact_ref")
    previous = context.load_latest_checkpoint()
    sequence = int(previous.get("sequence", 0)) + 1 if isinstance(previous, dict) else 1
    checkpoint = create_checkpoint(
        task_id=str(context.task_id),
        sequence=sequence,
        state="checkpointed",
        task_spec_version=PROTOCOL_VERSION,
        task_state={
            "stage": "council_result_verified",
            "status": "verified",
            "request_id": payload["request_id"],
            "session_id": payload["session_id"],
            "correlation_id": payload.get("correlation_id"),
            "mode": payload.get("mode"),
            "parent_task_id": payload.get("parent_task_id"),
            "parent_task_ref": payload.get("parent_task_ref"),
            "result_artifact_ref": artifact_ref,
            "result_sha256": result_sha256,
            "council_result": normalized,
            "model_output_is_untrusted_data": True,
        },
        budgets={},
        approvals={},
        artifact_refs=[artifact_ref],
        previous_checkpoint_hash=(
            previous.get("checkpoint_hash") if isinstance(previous, dict) else None
        ),
    )
    if not context.save_checkpoint(checkpoint):
        return TaskExecutionResult("retry", "council_result_checkpoint_failed", 90)

    parent_task_id = payload.get("parent_task_id")
    if isinstance(parent_task_id, int) and not isinstance(parent_task_id, bool):
        try:
            resumed = context.store.record_council_resume_event(
                parent_task_id=parent_task_id,
                result_task_id=context.task_id,
                worker_id=context.worker_id,
                council_request_id=payload["request_id"],
                result_artifact_ref=artifact_ref,
                result_sha256=result_sha256,
            )
        except (OSError, RuntimeError):
            return TaskExecutionResult("retry", "council_parent_resume_unavailable", 90)
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "council_parent_resume_rejected")
        if not resumed.get("accepted"):
            reason = resumed.get("reason")
            safe_reason = reason if isinstance(reason, str) and reason.replace("_", "").isalnum() else "parent_resume_rejected"
            return TaskExecutionResult("blocked", safe_reason)
    return TaskExecutionResult("completed")
