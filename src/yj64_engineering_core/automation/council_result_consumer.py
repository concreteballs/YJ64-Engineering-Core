"""Consume validated Council results and persist a resumable parent handoff.

Council prose remains untrusted analytical data. This consumer never interprets
model text as commands, approvals, or executable instructions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .checkpoints import create_checkpoint, verify_checkpoint
from .council_gateway import PROTOCOL_VERSION
from .council_tasks import _payload, load_council_result_artifact
from .worker import TaskExecutionResult


_RESULT_LIST_FIELDS = (
    "claims", "evidence", "dissent", "unresolved_questions",
    "assumptions", "limitations",
)
_OUTCOMES = {
    "consensus", "qualified_consensus",
    "unresolved_disagreement", "insufficient_evidence",
}
_TERMINAL_STATUSES = {"blocked", "failed", "cancelled"}


def _validated_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate the structured result contract without trusting its prose."""
    outcome = result.get("outcome")
    summary = result.get("summary")
    if outcome not in _OUTCOMES:
        raise ValueError("invalid_council_result_outcome")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 20000:
        raise ValueError("invalid_council_result_summary")

    normalized: dict[str, Any] = {"outcome": outcome, "summary": summary}
    for field in _RESULT_LIST_FIELDS:
        value = result.get(field, [])
        if not isinstance(value, list) or len(value) > 500:
            raise ValueError("invalid_council_result_" + field)
        normalized[field] = value
    for field in ("participant_positions", "tests_and_simulations"):
        value = result.get(field, [])
        if not isinstance(value, list) or len(value) > 500:
            raise ValueError("invalid_council_result_" + field)
        normalized[field] = value
    for field in ("rounds_completed", "completion_reason", "voting_summary"):
        if field in result:
            normalized[field] = result[field]
    return normalized


def _validated_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    from .browser_agent_bridge import validate_envelope

    envelope = validate_envelope(payload.get("browser_agent_envelope", {}))
    envelope_payload = envelope.get("payload", {})
    request_id = payload.get("request_id")
    session_id = payload.get("session_id")
    execution_status = payload.get("execution_status")
    artifact_ref = payload.get("result_artifact_ref")
    parent_task_id = payload.get("parent_task_id")
    parent_task_ref = payload.get("parent_task_ref")

    if parent_task_id is not None:
        if (
            not isinstance(parent_task_id, int) or isinstance(parent_task_id, bool)
            or parent_task_id < 1 or parent_task_ref is not None
        ):
            raise ValueError("invalid_council_parent_task_identity")
        expected_envelope_task_id: int | str = parent_task_id
    elif parent_task_ref is not None:
        if (
            not isinstance(parent_task_ref, str)
            or not parent_task_ref.strip() or len(parent_task_ref) > 128
        ):
            raise ValueError("invalid_council_parent_task_reference")
        expected_envelope_task_id = parent_task_ref
    else:
        expected_envelope_task_id = request_id

    if (
        envelope.get("message_type") != "council_result"
        or envelope.get("task_id") != expected_envelope_task_id
        or envelope.get("idempotency_key") != f"council-result:{request_id}"
        or envelope_payload.get("request_id") != request_id
        or envelope_payload.get("session_id") != session_id
        or envelope_payload.get("execution_status") != execution_status
        or envelope_payload.get("result_artifact_ref") != artifact_ref
        or envelope_payload.get("source") != "yj64_native_council"
        or payload.get("source") != "yj64_native_council"
        or not isinstance(request_id, str) or not request_id
        or not isinstance(session_id, str) or not session_id
        or execution_status not in ({"completed"} | _TERMINAL_STATUSES)
        or not isinstance(artifact_ref, str) or not artifact_ref
    ):
        raise ValueError("council result envelope binding mismatch")
    return envelope


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _save_result_checkpoint(
    context: Any, *, stage: str, state: dict[str, Any], artifact_ref: str,
) -> bool:
    previous = context.load_latest_checkpoint()
    if previous is not None:
        verify_checkpoint(previous)
        previous_state = previous.get("task_state", {})
        if isinstance(previous_state, dict) and previous_state.get("stage") == stage:
            same_identity = all(
                previous_state.get(key) == state.get(key)
                for key in ("request_id", "session_id", "result_artifact_ref", "result_sha256")
            )
            if same_identity:
                return True
            raise ValueError("council result checkpoint identity conflict")
        sequence = previous["sequence"] + 1
        previous_hash = previous["checkpoint_hash"]
    else:
        sequence = 1
        previous_hash = None
    checkpoint = create_checkpoint(
        task_id=str(context.task_id),
        sequence=sequence,
        state="checkpointed",
        task_spec_version=PROTOCOL_VERSION,
        task_state=state,
        budgets={},
        approvals={},
        artifact_refs=[artifact_ref],
        previous_checkpoint_hash=previous_hash,
    )
    return bool(context.save_checkpoint(checkpoint))


def _resume_parent_if_present(
    context: Any, payload: dict[str, Any], artifact_ref: str,
    result_sha256: str, resume_payload: dict[str, Any],
) -> dict[str, Any]:
    parent_task_id = payload.get("parent_task_id")
    if parent_task_id is None:
        # A string parent_task_ref belongs to an external task namespace. Keep
        # the result on this durable result task; do not guess a numeric queue ID.
        return {"accepted": True, "not_applicable": True}
    request_id = payload.get("request_id")
    resumed = context.record_council_resume_event(
        parent_task_id, request_id, artifact_ref, result_sha256, resume_payload,
    )
    if not isinstance(resumed, dict):
        raise RuntimeError("council parent resume returned an invalid response")
    return resumed


def _resume_decision(resumed: dict[str, Any]) -> TaskExecutionResult:
    if resumed.get("accepted"):
        return TaskExecutionResult("completed")
    # Missing, finished, or mismatched parents are terminal handoff failures;
    # retrying cannot safely recreate the original task.
    return TaskExecutionResult("blocked", "council_parent_not_resumable")


def handle_council_result_ready(
    task: dict,
    context: Any,
    *,
    artifact_store_factory: Callable[[], Any] | None = None,
) -> TaskExecutionResult:
    """Verify a Council result and atomically publish it to its waiting parent."""
    try:
        payload = _payload(task)
        envelope = _validated_envelope(payload)
        execution_status = payload["execution_status"]
        artifact_ref = payload["result_artifact_ref"]

        if execution_status in _TERMINAL_STATUSES:
            reason = payload.get("reason")
            safe_reason = (
                reason if isinstance(reason, str)
                and reason.replace("_", "").replace("-", "").isalnum()
                and len(reason) <= 120 else "council_result_not_completed"
            )
            terminal = {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": payload["request_id"],
                "session_id": payload["session_id"],
                "status": execution_status,
                "reason": safe_reason,
            }
            digest = _digest(terminal)
            state = {
                "stage": "council_result_terminal",
                "status": execution_status,
                "reason": safe_reason,
                "parent_task_id": payload.get("parent_task_id"),
                "parent_task_ref": payload.get("parent_task_ref"),
                "request_id": payload["request_id"],
                "session_id": payload["session_id"],
                "result_artifact_ref": artifact_ref,
                "result_sha256": digest,
                "council_terminal_result": terminal,
            }
            if not _save_result_checkpoint(
                context, stage="council_result_terminal",
                state=state, artifact_ref=artifact_ref,
            ):
                return TaskExecutionResult("retry", "council_result_checkpoint_failed", 90)
            resume_payload = {
                "request_id": payload["request_id"],
                "session_id": payload["session_id"],
                "execution_status": execution_status,
                "terminal": terminal,
                "result": None,
                "model_output_is_untrusted_data": True,
            }
        else:
            result = load_council_result_artifact(
                payload, artifact_store_factory=artifact_store_factory,
            )
            normalized = _validated_result(result)
            digest = _digest(result)
            state = {
                "stage": "council_result_verified",
                "status": "verified",
                "request_id": payload["request_id"],
                "session_id": payload["session_id"],
                "correlation_id": payload.get("correlation_id"),
                "mode": payload.get("mode"),
                "parent_task_id": payload.get("parent_task_id"),
                "parent_task_ref": payload.get("parent_task_ref"),
                "result_artifact_ref": artifact_ref,
                "result_sha256": digest,
                "council_result": normalized,
                "model_output_is_untrusted_data": True,
            }
            if not _save_result_checkpoint(
                context, stage="council_result_verified",
                state=state, artifact_ref=artifact_ref,
            ):
                return TaskExecutionResult("retry", "council_result_checkpoint_failed", 90)
            resume_payload = {
                "request_id": payload["request_id"],
                "session_id": payload["session_id"],
                "execution_status": "completed",
                "result": normalized,
                "terminal": None,
                "model_output_is_untrusted_data": True,
            }
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_result")
    except (OSError, RuntimeError):
        return TaskExecutionResult("retry", "council_result_artifact_unavailable", 90)

    try:
        resumed = _resume_parent_if_present(
            context, payload, artifact_ref, digest, resume_payload,
        )
    except ValueError:
        return TaskExecutionResult("blocked", "council_parent_resume_invalid")
    except (OSError, RuntimeError):
        return TaskExecutionResult("retry", "council_parent_resume_failed", 90)
    return _resume_decision(resumed)


