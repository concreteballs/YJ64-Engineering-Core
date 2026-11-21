"""Durable queue handlers for asynchronous YJ-64 council requests.

A submit task creates/reuses one remote council session and immediately releases
its worker. Poll tasks are separate queue items. A completed result is stored as
an immutable private artifact and handed back as a council_result_ready task for
the engineering-agent workflow to consume.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .browser_agent_bridge import create_envelope, validate_envelope
from .checkpoints import create_checkpoint
from .council_gateway import (
    CouncilGatewayClient,
    CouncilGatewayError,
    CouncilRequest,
    PROTOCOL_VERSION,
)
from .worker import TaskExecutionResult


SUBMIT_TASK = "submit_council_request"
POLL_TASK = "poll_council_request"
RESULT_READY_TASK = "council_result_ready"
DEFAULT_MAX_POLLS = 288


def enqueue_council_request(
    store: Any,
    *,
    mode: str,
    title: str,
    prompt: str,
    correlation_id: str,
    idempotency_key: str,
    context: Mapping[str, Any] | None = None,
    evidence_refs: list[str] | tuple[str, ...] = (),
    parent_task_id: int | None = None,
    parent_task_ref: str | None = None,
    max_rounds: int = 3,
    timeout_seconds: int = 1800,
    max_output_tokens: int = 12000,
    voting_enabled: bool = False,
    weighted_voting_enabled: bool = False,
    allow_early_stop: bool = True,
    submitted_at: str | None = None,
    max_poll_count: int = DEFAULT_MAX_POLLS,
) -> dict[str, Any]:
    """Enqueue one external council request using the existing PostgreSQL queue."""
    if isinstance(evidence_refs, str):
        raise ValueError("evidence_refs must be a list or tuple of references")
    request = CouncilRequest(
        mode=mode,
        title=title,
        prompt=prompt,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        context=context,
        evidence_refs=tuple(evidence_refs),
        max_rounds=max_rounds,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        voting_enabled=voting_enabled,
        weighted_voting_enabled=weighted_voting_enabled,
        allow_early_stop=allow_early_stop,
    )
    request.to_payload("yj64-engineering-core")
    if parent_task_id is not None and (
        not isinstance(parent_task_id, int) or isinstance(parent_task_id, bool)
        or parent_task_id < 1
    ):
        raise ValueError("parent_task_id must be a positive integer or None")
    if parent_task_ref is not None and (
        not isinstance(parent_task_ref, str) or not parent_task_ref.strip() or len(parent_task_ref) > 128
    ):
        raise ValueError("parent_task_ref must be a non-empty string of at most 128 characters")
    if parent_task_id is not None and parent_task_ref is not None:
        raise ValueError("provide parent_task_id or parent_task_ref, not both")
    if submitted_at is None:
        submitted = datetime.now(timezone.utc)
    else:
        if not isinstance(submitted_at, str):
            raise ValueError("submitted_at must be a timezone-aware ISO timestamp")
        try:
            submitted = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("submitted_at must be a timezone-aware ISO timestamp") from None
        if submitted.tzinfo is None:
            raise ValueError("submitted_at must be a timezone-aware ISO timestamp")
        submitted = submitted.astimezone(timezone.utc)
    submitted_at_normalized = submitted.isoformat().replace("+00:00", "Z")
    if (
        not isinstance(max_poll_count, int) or isinstance(max_poll_count, bool)
        or not 1 <= max_poll_count <= 2016
    ):
        raise ValueError("max_poll_count must be between 1 and 2016 (seven days at five-minute polling)")

    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "request": {
            "mode": request.mode,
            "title": request.title,
            "prompt": request.prompt,
            "correlation_id": request.correlation_id,
            "idempotency_key": request.idempotency_key,
            "context": dict(request.context or {}),
            "evidence_refs": list(request.evidence_refs),
            "max_rounds": request.max_rounds,
            "timeout_seconds": request.timeout_seconds,
            "max_output_tokens": request.max_output_tokens,
            "voting_enabled": request.voting_enabled,
            "weighted_voting_enabled": request.weighted_voting_enabled,
            "allow_early_stop": request.allow_early_stop,
        },
        "parent_task_id": parent_task_id,
        "parent_task_ref": parent_task_ref,
        "submitted_at": submitted_at_normalized,
        "max_poll_count": max_poll_count,
    }
    key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return store.enqueue_task(
        SUBMIT_TASK,
        payload,
        dedupe_key=f"council-submit:{key_digest}",
        max_attempts=5,
    )


def enqueue_council_request_from_envelope(
    store: Any, envelope: Mapping[str, Any]
) -> dict[str, Any]:
    """Accept a scoped browser-agent council_request envelope into the task queue."""
    message = validate_envelope(envelope)
    if message.get("message_type") != "council_request":
        raise ValueError("browser-agent message is not a council_request")
    request = message.get("payload")
    if not isinstance(request, dict):
        raise ValueError("council_request payload must be an object")
    task_ref = message["task_id"]
    return enqueue_council_request(
        store,
        mode=request.get("mode"),
        title=request.get("title"),
        prompt=request.get("prompt"),
        correlation_id=request.get("correlation_id") or message["message_id"],
        idempotency_key=message["idempotency_key"],
        context=request.get("context", {}),
        evidence_refs=request.get("evidence_refs", []),
        parent_task_id=task_ref if isinstance(task_ref, int) else None,
        parent_task_ref=task_ref if isinstance(task_ref, str) else None,
        max_rounds=request.get("max_rounds", 3),
        timeout_seconds=request.get("timeout_seconds", 1800),
        max_output_tokens=request.get("max_output_tokens", 12000),
        voting_enabled=request.get("voting_enabled", False),
        weighted_voting_enabled=request.get("weighted_voting_enabled", False),
        allow_early_stop=request.get("allow_early_stop", True),
        submitted_at=message["created_at"],
        max_poll_count=request.get("max_poll_count", DEFAULT_MAX_POLLS),
    )


def _payload(task: Mapping[str, Any]) -> dict[str, Any]:
    raw = task.get("payload")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raise ValueError("invalid_task_payload") from None
    if not isinstance(raw, dict) or raw.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("invalid_task_payload")
    return raw


def _payload_digest(payload: Mapping[str, Any]) -> str:
    """Bind a parent resume to the exact durable task payload."""
    try:
        encoded = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("parent_task_payload_must_be_finite_json") from None
    return hashlib.sha256(encoded).hexdigest()


def _client(factory: Callable[[], CouncilGatewayClient] | None) -> CouncilGatewayClient:
    return factory() if factory is not None else CouncilGatewayClient.from_environment()


def _checkpoint(context: Any, task: Mapping[str, Any], state: dict[str, Any]) -> bool:
    previous = context.load_latest_checkpoint()
    sequence = int(previous.get("sequence", 0)) + 1 if isinstance(previous, dict) else 1
    previous_hash = previous.get("checkpoint_hash") if isinstance(previous, dict) else None
    checkpoint = create_checkpoint(
        task_id=str(context.task_id),
        sequence=sequence,
        state="checkpointed",
        task_spec_version=PROTOCOL_VERSION,
        task_state=state,
        budgets={},
        approvals={"external_council_request": "authorized_by_calling_workflow"},
        artifact_refs=state.get("artifact_refs", []),
        previous_checkpoint_hash=previous_hash,
    )
    return bool(context.save_checkpoint(checkpoint))


def _queue_poll(
    context: Any,
    payload: dict[str, Any],
    *,
    request_id: str,
    session_id: str,
    generation: int,
) -> dict[str, Any]:
    poll_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "session_id": session_id,
        "parent_task_id": payload.get("parent_task_id"),
        "parent_task_ref": payload.get("parent_task_ref"),
        "submitted_at": payload["submitted_at"],
        "correlation_id": payload["request"]["correlation_id"],
        "idempotency_key": payload["request"]["idempotency_key"],
        "mode": payload["request"]["mode"],
        "poll_generation": generation,
        "max_poll_count": payload["max_poll_count"],
    }
    return context.store.enqueue_task(
        POLL_TASK,
        poll_payload,
        dedupe_key=f"council-poll:{request_id}:{generation}",
        max_attempts=5,
    )


def handle_council_request_in_parent_task(
    task: dict,
    context: Any,
    *,
    client_factory: Callable[[], CouncilGatewayClient] | None = None,
    continuation_handler: Callable[[dict, Any, dict], TaskExecutionResult] | None = None,
) -> TaskExecutionResult:
    """Submit/suspend or resume the same parent task through its registered continuation.

    A parent must already have a verified, non-empty checkpoint before Council is
    contacted. The checkpoint preserves the original goal, context, decisions,
    history, budgets, approvals, and artifacts. Its payload digest binds the
    resumed callback to the same durable queue row. Council prose remains
    untrusted analytical data and is never interpreted as commands.
    """
    if continuation_handler is not None and not callable(continuation_handler):
        return TaskExecutionResult("blocked", "council_resume_continuation_invalid")
    if not isinstance(task, dict) or task.get("task_id") != context.task_id:
        return TaskExecutionResult("blocked", "council_parent_task_identity_invalid")

    loader = getattr(context, "load_council_resume", None)
    if not callable(loader):
        return TaskExecutionResult("blocked", "council_resume_loader_unavailable")
    try:
        resume = loader()
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "council_resume_invalid")
    except Exception:
        return TaskExecutionResult("retry", "council_resume_load_failed", 90)

    if resume is not None:
        parent_state = resume.get("parent_task_state") if isinstance(resume, dict) else None
        try:
            current_payload_digest = _payload_digest(_payload(task))
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "council_resume_parent_payload_invalid")
        expected_payload_digest = (
            parent_state.get("parent_task_payload_sha256")
            if isinstance(parent_state, dict) else None
        )
        if (
            expected_payload_digest is not None
            and expected_payload_digest != current_payload_digest
        ):
            return TaskExecutionResult("blocked", "council_resume_parent_payload_mismatch")
        if (
            not isinstance(resume, dict)
            or resume.get("parent_task_id") != context.task_id
            or resume.get("model_output_is_untrusted_data") is not True
            or not isinstance(resume.get("request_id"), str)
            or not resume.get("request_id")
            or not isinstance(parent_state, dict)
            or parent_state.get("expected_council_request_id") != resume.get("request_id")
        ):
            return TaskExecutionResult("blocked", "council_resume_identity_invalid")
        if continuation_handler is None:
            return TaskExecutionResult("blocked", "council_resume_continuation_unconfigured")
        execution_status = resume.get("execution_status")
        if execution_status not in {"completed", "blocked", "failed", "cancelled"}:
            return TaskExecutionResult("blocked", "council_resume_status_invalid")
        decision_assessment = None
        if execution_status == "completed":
            try:
                from .council_decision_adapter import build_council_decision_assessment
                decision_assessment = build_council_decision_assessment(resume)
            except (TypeError, ValueError, KeyError):
                return TaskExecutionResult("blocked", "council_decision_assessment_invalid")
        resume_for_handler = dict(resume)
        resume_for_handler["decision_assessment"] = decision_assessment
        try:
            decision = continuation_handler(task, context, resume_for_handler)
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "council_resume_continuation_invalid")
        except Exception:
            return TaskExecutionResult("retry", "council_resume_continuation_failed", 90)
        if not isinstance(decision, TaskExecutionResult):
            return TaskExecutionResult("blocked", "council_resume_continuation_invalid")
        return decision

    try:
        payload = _payload(task)
        raw = payload.get("request")
        if not isinstance(raw, dict):
            return TaskExecutionResult("blocked", "invalid_council_request")
        request = CouncilRequest(
            mode=raw.get("mode"), title=raw.get("title"), prompt=raw.get("prompt"),
            correlation_id=raw.get("correlation_id"),
            idempotency_key=raw.get("idempotency_key"),
            context=raw.get("context", {}),
            evidence_refs=tuple(raw.get("evidence_refs", [])),
            max_rounds=raw.get("max_rounds", 3),
            timeout_seconds=raw.get("timeout_seconds", 1800),
            max_output_tokens=raw.get("max_output_tokens", 12000),
            voting_enabled=raw.get("voting_enabled", False),
            weighted_voting_enabled=raw.get("weighted_voting_enabled", False),
            allow_early_stop=raw.get("allow_early_stop", True),
        )
        payload_digest = _payload_digest(payload)
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_request")

    from .checkpoints import verify_checkpoint
    try:
        previous = context.load_latest_checkpoint()
        if previous is None:
            return TaskExecutionResult("blocked", "council_parent_checkpoint_missing")
        verify_checkpoint(previous)
        if previous.get("task_id") != str(context.task_id):
            return TaskExecutionResult("blocked", "parent_checkpoint_identity_mismatch")
        previous_state = previous.get("task_state")
        if not isinstance(previous_state, dict) or not previous_state:
            return TaskExecutionResult("blocked", "council_parent_context_missing")
        previous_state = dict(previous_state)
        stored_payload_digest = previous_state.get("parent_task_payload_sha256")
        if stored_payload_digest is not None and stored_payload_digest != payload_digest:
            return TaskExecutionResult("blocked", "council_parent_payload_mismatch")

        # If a prior attempt persisted the waiting checkpoint but lost its lease
        # before suspension completed, re-release the same parent lease. Do not
        # submit a second Council request or create another poll generation.
        if previous_state.get("stage") == "waiting_council":
            request_id = previous_state.get("expected_council_request_id")
            if (
                not isinstance(request_id, str) or not request_id
                or previous_state.get("request_id") != request_id
                or not isinstance(previous_state.get("session_id"), str)
                or not previous_state.get("session_id")
                or previous_state.get("idempotency_key") != request.idempotency_key
                or (
                    stored_payload_digest is not None
                    and stored_payload_digest != payload_digest
                )
            ):
                return TaskExecutionResult("blocked", "council_parent_wait_identity_mismatch")
            try:
                if not context.suspend_for_council(previous, request_id):
                    return TaskExecutionResult("retry", "council_parent_suspend_failed", 90)
            except (RuntimeError, ValueError):
                return TaskExecutionResult("retry", "council_parent_suspend_failed", 90)
            return TaskExecutionResult("suspended")
        if previous_state.get("stage") in {"council_resume_ready", "parent_resume_ready"}:
            return TaskExecutionResult("blocked", "council_parent_resume_checkpoint_invalid")
    except ValueError:
        return TaskExecutionResult("blocked", "invalid_parent_checkpoint")
    except Exception:
        return TaskExecutionResult("retry", "council_parent_checkpoint_unavailable", 90)

    try:
        accepted = _client(client_factory).submit(request)
    except CouncilGatewayError as exc:
        if exc.retryable:
            return TaskExecutionResult("retry", exc.classification, min(900, max(30, exc.retry_after_seconds or 90)))
        return TaskExecutionResult("blocked", exc.classification)
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_request")

    parent_payload = dict(payload)
    parent_payload["parent_task_id"] = context.task_id
    parent_payload.pop("parent_task_ref", None)
    parent_payload.setdefault("submitted_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    parent_payload.setdefault("max_poll_count", DEFAULT_MAX_POLLS)
    queued = _queue_poll(
        context, parent_payload, request_id=accepted["request_id"],
        session_id=accepted["session_id"], generation=0,
    )
    if not queued.get("enqueued") and not queued.get("duplicate"):
        return TaskExecutionResult("retry", "council_poll_enqueue_failed", 90)

    task_state = dict(previous_state)
    previous_stage = task_state.get("stage")
    if previous_stage is not None:
        task_state.setdefault("stage_before_council", previous_stage)
    task_state.update({
        "stage": "waiting_council",
        "status": "waiting",
        "parent_task_payload_sha256": payload_digest,
        "expected_council_request_id": accepted["request_id"],
        "request_id": accepted["request_id"],
        "session_id": accepted["session_id"],
        "correlation_id": accepted["correlation_id"],
        "idempotency_key": accepted["idempotency_key"],
        "submitted_at": parent_payload["submitted_at"],
        "council_wait": {
            "request_id": accepted["request_id"],
            "session_id": accepted["session_id"],
            "mode": request.mode,
            "submitted_at": parent_payload["submitted_at"],
        },
    })
    checkpoint = create_checkpoint(
        task_id=str(context.task_id),
        sequence=previous["sequence"] + 1,
        state="checkpointed",
        task_spec_version=previous["task_spec_version"],
        task_state=task_state,
        budgets=previous.get("budgets", {}),
        approvals=previous.get("approvals", {}),
        artifact_refs=previous.get("artifact_refs", []),
        previous_checkpoint_hash=previous["checkpoint_hash"],
    )
    try:
        if not context.suspend_for_council(checkpoint, accepted["request_id"]):
            return TaskExecutionResult("retry", "council_parent_suspend_failed", 90)
    except (RuntimeError, ValueError):
        return TaskExecutionResult("retry", "council_parent_suspend_failed", 90)
    return TaskExecutionResult("suspended")


def handle_submit_council_request(
    task: dict,
    context: Any,
    *,
    client_factory: Callable[[], CouncilGatewayClient] | None = None,
) -> TaskExecutionResult:
    """Submit idempotently, persist the accepted IDs, queue polling, then release."""
    try:
        payload = _payload(task)
        raw = payload.get("request")
        if not isinstance(raw, dict):
            return TaskExecutionResult("blocked", "invalid_council_request")
        request = CouncilRequest(
            mode=raw.get("mode"),
            title=raw.get("title"),
            prompt=raw.get("prompt"),
            correlation_id=raw.get("correlation_id"),
            idempotency_key=raw.get("idempotency_key"),
            context=raw.get("context", {}),
            evidence_refs=tuple(raw.get("evidence_refs", [])),
            max_rounds=raw.get("max_rounds", 3),
            timeout_seconds=raw.get("timeout_seconds", 1800),
            max_output_tokens=raw.get("max_output_tokens", 12000),
            voting_enabled=raw.get("voting_enabled", False),
            weighted_voting_enabled=raw.get("weighted_voting_enabled", False),
            allow_early_stop=raw.get("allow_early_stop", True),
        )
        accepted = _client(client_factory).submit(request)
    except CouncilGatewayError as exc:
        if exc.retryable:
            delay = min(900, max(30, exc.retry_after_seconds or 90))
            return TaskExecutionResult("retry", exc.classification, delay)
        return TaskExecutionResult("blocked", exc.classification)
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_request")

    state = {
        "stage": "accepted",
        "request_id": accepted["request_id"],
        "session_id": accepted["session_id"],
        "correlation_id": accepted["correlation_id"],
        "idempotency_key": accepted["idempotency_key"],
        "remote_status": accepted["status"],
        "parent_task_id": payload.get("parent_task_id"),
        "parent_task_ref": payload.get("parent_task_ref"),
        "submitted_at": payload["submitted_at"],
    }
    if not _checkpoint(context, task, state):
        # Re-submission is safe because the remote API receives the same key.
        return TaskExecutionResult("retry", "council_checkpoint_persistence_failed", 90)
    queued = _queue_poll(
        context, payload,
        request_id=accepted["request_id"],
        session_id=accepted["session_id"],
        generation=0,
    )
    if not queued.get("enqueued") and not queued.get("duplicate"):
        return TaskExecutionResult("retry", "council_poll_enqueue_failed", 90)
    return TaskExecutionResult("completed")


def _enqueue_result_ready(
    context: Any,
    payload: dict[str, Any],
    *,
    execution_status: str,
    result_artifact_ref: str | None = None,
    outcome: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    request_id = payload["request_id"]
    if execution_status != "completed" and result_artifact_ref is None:
        result_artifact_ref = f"council-terminal://{request_id}/{execution_status}"
    envelope_task_id = (
        payload.get("parent_task_id")
        or payload.get("parent_task_ref")
        or request_id
    )
    result_payload = {
        "request_id": request_id,
        "session_id": payload["session_id"],
        "correlation_id": payload.get("correlation_id"),
        "mode": payload.get("mode"),
        "execution_status": execution_status,
        "substantive_outcome": outcome,
        "result_artifact_ref": result_artifact_ref,
        "reason": reason,
        "source": "yj64_native_council",
    }
    result_envelope = create_envelope(
        message_type="council_result",
        task_id=envelope_task_id,
        idempotency_key=f"council-result:{request_id}",
        payload=result_payload,
        now=datetime.fromisoformat(payload["submitted_at"].replace("Z", "+00:00")),
        message_id=hashlib.sha256(f"council-result:{request_id}".encode("utf-8")).hexdigest()[:32],
        ttl_seconds=2592000,
    )
    handoff = {
        "protocol_version": PROTOCOL_VERSION,
        **result_payload,
        "parent_task_id": payload.get("parent_task_id"),
        "parent_task_ref": payload.get("parent_task_ref"),
        "browser_agent_envelope": result_envelope,
    }
    return context.store.enqueue_task(
        RESULT_READY_TASK,
        handoff,
        dedupe_key=f"council-result:{request_id}",
        max_attempts=5,
    )


def load_council_result_artifact(
    handoff: Mapping[str, Any],
    *,
    artifact_store_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Load and identity-check a completed council result for the agent consumer."""
    if not isinstance(handoff, Mapping):
        raise ValueError("council result handoff must be an object")
    message = dict(handoff)
    if "payload" in message and "browser_agent_envelope" not in message:
        message = _payload(message)
    envelope = validate_envelope(message.get("browser_agent_envelope", {}))
    if envelope.get("message_type") != "council_result":
        raise ValueError("handoff does not contain a council_result envelope")
    envelope_payload = envelope.get("payload", {})
    request_id = message.get("request_id")
    session_id = message.get("session_id")
    if (
        message.get("execution_status") not in {"completed", "blocked", "failed", "cancelled"}
        or not isinstance(request_id, str)
        or not isinstance(session_id, str)
        or envelope_payload.get("request_id") != request_id
        or envelope_payload.get("session_id") != session_id
    ):
        raise ValueError("council result handoff identity or status mismatch")
    artifact_ref = message.get("result_artifact_ref")
    if not isinstance(artifact_ref, str) or not artifact_ref:
        raise ValueError("completed council result is missing its artifact reference")
    if artifact_store_factory is not None:
        artifact_store = artifact_store_factory()
    else:
        from .supabase_storage import SupabaseStorageArtifactStore
        artifact_store = SupabaseStorageArtifactStore.from_environment()
    content = artifact_store.get(artifact_ref)
    try:
        result = json.loads(content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("council result artifact is not valid JSON") from None
    if (
        not isinstance(result, dict)
        or result.get("request_id") != request_id
        or result.get("session_id") != session_id
        or result.get("status") != message.get("execution_status")
    ):
        raise ValueError("council result artifact identity mismatch")
    return result


def handle_poll_council_request(
    task: dict,
    context: Any,
    *,
    client_factory: Callable[[], CouncilGatewayClient] | None = None,
    artifact_store_factory: Callable[[], Any] | None = None,
) -> TaskExecutionResult:
    """Poll once; never wait in-process and never keep a worker leased between polls."""
    try:
        payload = _payload(task)
        request_id = payload.get("request_id")
        session_id = payload.get("session_id")
        if not isinstance(request_id, str) or not request_id:
            return TaskExecutionResult("blocked", "invalid_council_request_id")
        if not isinstance(session_id, str) or not session_id:
            return TaskExecutionResult("blocked", "invalid_council_session_id")
        generation = payload.get("poll_generation")
        maximum = payload.get("max_poll_count")
        if (
            not isinstance(generation, int) or isinstance(generation, bool) or generation < 0
            or not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 10000
        ):
            return TaskExecutionResult("blocked", "invalid_council_poll_state")
        client = _client(client_factory)
        status = client.get_status(request_id)
    except CouncilGatewayError as exc:
        if exc.retryable:
            return TaskExecutionResult("retry", exc.classification, min(900, max(30, exc.retry_after_seconds or 90)))
        handoff = _enqueue_result_ready(
            context, payload, execution_status="blocked",
            reason=exc.classification,
        )
        if not handoff.get("enqueued") and not handoff.get("duplicate"):
            return TaskExecutionResult("retry", "council_result_handoff_failed", 90)
        return TaskExecutionResult("completed")
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_council_poll_task")

    if status["session_id"] != session_id:
        handoff = _enqueue_result_ready(
            context, payload, execution_status="blocked",
            reason="council_session_id_mismatch",
        )
        if not handoff.get("enqueued") and not handoff.get("duplicate"):
            return TaskExecutionResult("retry", "council_result_handoff_failed", 90)
        return TaskExecutionResult("completed")

    state = {
        "stage": "poll",
        "request_id": request_id,
        "session_id": session_id,
        "remote_status": status["status"],
        "poll_generation": generation,
        "submitted_at": payload["submitted_at"],
    }
    if not _checkpoint(context, task, state):
        return TaskExecutionResult("retry", "council_checkpoint_persistence_failed", 90)

    if status["status"] in {"accepted", "running"}:
        if generation + 1 >= maximum:
            handoff = _enqueue_result_ready(
                context, payload, execution_status="blocked",
                reason="council_poll_limit_reached",
            )
            if not handoff.get("enqueued") and not handoff.get("duplicate"):
                return TaskExecutionResult("retry", "council_result_handoff_failed", 90)
            return TaskExecutionResult("completed")
        queued = _queue_poll_from_poll_task(context, payload, generation + 1)
        if not queued.get("enqueued") and not queued.get("duplicate"):
            return TaskExecutionResult("retry", "council_poll_enqueue_failed", 90)
        return TaskExecutionResult("completed")

    if status["status"] == "completed":
        try:
            result = client.get_result(request_id, session_id)
            if artifact_store_factory is not None:
                artifact_store = artifact_store_factory()
            else:
                from .supabase_storage import SupabaseStorageArtifactStore
                artifact_store = SupabaseStorageArtifactStore.from_environment()
            content = json.dumps(
                result, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            artifact_ref = artifact_store.put(
                namespace=f"council/{request_id}",
                content=content,
                content_type="application/json",
            )
        except CouncilGatewayError as exc:
            if exc.retryable:
                return TaskExecutionResult("retry", exc.classification, 90)
            handoff = _enqueue_result_ready(
                context, payload, execution_status="blocked",
                reason=exc.classification,
            )
            if not handoff.get("enqueued") and not handoff.get("duplicate"):
                return TaskExecutionResult("retry", "council_result_handoff_failed", 90)
            return TaskExecutionResult("completed")
        except (RuntimeError, OSError, ValueError, TypeError):
            return TaskExecutionResult("retry", "council_result_persistence_failed", 90)
        handoff = _enqueue_result_ready(
            context, payload,
            execution_status="completed",
            result_artifact_ref=artifact_ref,
            outcome=result["outcome"],
        )
    else:
        handoff = _enqueue_result_ready(
            context, payload,
            execution_status=status["status"],
            reason=f"council_{status['status']}",
        )
    if not handoff.get("enqueued") and not handoff.get("duplicate"):
        return TaskExecutionResult("retry", "council_result_handoff_failed", 90)
    return TaskExecutionResult("completed")


def _queue_poll_from_poll_task(
    context: Any, payload: dict[str, Any], generation: int
) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload["poll_generation"] = generation
    return context.store.enqueue_task(
        POLL_TASK,
        next_payload,
        dedupe_key=f"council-poll:{payload['request_id']}:{generation}",
        max_attempts=5,
    )
