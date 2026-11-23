"""Bridge validated Council resumes to the existing approved EngineeringDispatcher.

The adapter creates no worker, queue, scheduler, or task loop. Human approval,
permission snapshots, and signature verification are injected by trusted host
code. Council-authored prose is never passed to those approval providers.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from .worker import TaskExecutionResult


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("council_executor_data_must_be_finite_json") from None


def _source_matches(resume: Mapping[str, Any], assessment: Mapping[str, Any],
                    policy: Mapping[str, Any], task_id: int) -> bool:
    expected = {
        "parent_task_id": task_id,
        "request_id": resume.get("request_id"),
        "session_id": resume.get("session_id"),
        "result_sha256": resume.get("result_sha256"),
    }
    if any(not isinstance(expected[key], str) or not expected[key] for key in (
        "request_id", "session_id", "result_sha256"
    )):
        return False
    assessment_source = assessment.get("source")
    policy_source = policy.get("source")
    if not isinstance(assessment_source, Mapping) or not isinstance(policy_source, Mapping):
        return False
    return dict(assessment_source) == expected and dict(policy_source) == expected


def make_approved_council_continuation(
    dispatcher: Any,
    *,
    approval_provider: Callable[[int, Mapping[str, Any]], Mapping[str, Any]],
    permission_snapshot_digest_provider: Callable[[int], str],
    verify_approval: Callable[[Mapping[str, Any]], bool],
    max_handler_result_bytes: int = 16384,
) -> Callable[[dict, Any, dict], TaskExecutionResult]:
    """Create a parent continuation that dispatches only an approved typed intent.

    Registered domain handlers must be idempotent by intent.idempotency_key.
    This key is stable across worker retries for the same task, policy, permission
    snapshot, operation, and resource scope. A handler must persist/deduplicate
    its own domain operation using that key before performing external effects.
    """
    if not callable(getattr(dispatcher, "dispatch_approved_intent", None)):
        raise TypeError("council_executor_requires_engineering_dispatcher")
    if not callable(approval_provider):
        raise TypeError("council_executor_requires_approval_provider")
    if not callable(permission_snapshot_digest_provider):
        raise TypeError("council_executor_requires_permission_snapshot_provider")
    if not callable(verify_approval):
        raise TypeError("council_executor_requires_approval_verifier")
    if (
        not isinstance(max_handler_result_bytes, int)
        or isinstance(max_handler_result_bytes, bool)
        or not 1024 <= max_handler_result_bytes <= 65536
    ):
        raise ValueError("council_executor_handler_result_limit_invalid")

    def continue_parent(task: dict, context: Any, resume: dict) -> TaskExecutionResult:
        task_id = getattr(context, "task_id", None)
        if (
            not isinstance(task, dict)
            or not isinstance(task_id, int)
            or isinstance(task_id, bool)
            or task_id < 1
            or task.get("task_id") != task_id
            or not isinstance(resume, dict)
            or resume.get("parent_task_id") != task_id
            or resume.get("model_output_is_untrusted_data") is not True
        ):
            return TaskExecutionResult("blocked", "council_executor_parent_identity_invalid")
        if resume.get("execution_status") != "completed":
            return TaskExecutionResult("blocked", "council_executor_result_not_completed")

        assessment = resume.get("decision_assessment")
        policy = resume.get("decision_policy")
        if not isinstance(assessment, Mapping) or not isinstance(policy, Mapping):
            return TaskExecutionResult("blocked", "council_executor_decision_missing")
        if (
            assessment.get("authority") != "advisory_only"
            or assessment.get("execution_allowed") is not False
            or policy.get("authority") != "advisory_only"
            or policy.get("execution_allowed") is not False
            or policy.get("requires_human_approval") is not True
            or policy.get("permission_changes") != []
            or policy.get("executable_actions") != []
            or not _source_matches(resume, assessment, policy, task_id)
        ):
            return TaskExecutionResult("blocked", "council_executor_decision_identity_invalid")
        try:
            if hashlib.sha256(_canonical(dict(assessment))).hexdigest() != policy.get(
                "input_digest_sha256"
            ):
                return TaskExecutionResult("blocked", "council_executor_assessment_digest_mismatch")
        except ValueError:
            return TaskExecutionResult("blocked", "council_executor_assessment_invalid")

        # Only the deterministic policy crosses into approval infrastructure.
        # Free-form Council summaries, claims, reasoning and evidence descriptions
        # are intentionally not passed to the provider.
        try:
            policy_for_approval = json.loads(_canonical(dict(policy)).decode("utf-8"))
            policy_snapshot_digest = hashlib.sha256(_canonical(policy_for_approval)).hexdigest()
            approval = approval_provider(task_id, policy_for_approval)
            if hashlib.sha256(_canonical(policy_for_approval)).hexdigest() != policy_snapshot_digest:
                return TaskExecutionResult("blocked", "council_executor_approval_provider_mutated_policy")
        except PermissionError:
            return TaskExecutionResult("blocked", "council_executor_human_approval_required")
        except (TypeError, ValueError):
            return TaskExecutionResult("blocked", "council_executor_approval_invalid")
        except Exception:
            return TaskExecutionResult("retry", "council_executor_approval_unavailable", 90)
        if not isinstance(approval, Mapping):
            return TaskExecutionResult("blocked", "council_executor_approval_missing")

        try:
            permission_digest = permission_snapshot_digest_provider(task_id)
        except Exception:
            return TaskExecutionResult("retry", "council_executor_permissions_unavailable", 90)

        try:
            dispatched = dispatcher.dispatch_approved_intent(
                decision_policy=policy,
                approval=approval,
                task_id=str(task_id),
                permission_snapshot_digest=permission_digest,
                verify_approval=verify_approval,
                execution_context=context,
            )
        except (TypeError, ValueError, LookupError):
            return TaskExecutionResult("blocked", "council_executor_dispatch_rejected")
        except Exception:
            return TaskExecutionResult("retry", "council_executor_handler_failed", 90)

        try:
            handler_result = dict(dispatched.result)
            encoded_result = _canonical(handler_result)
        except (TypeError, ValueError):
            return TaskExecutionResult("blocked", "council_executor_handler_result_invalid")
        if len(encoded_result) > max_handler_result_bytes:
            return TaskExecutionResult("blocked", "council_executor_handler_result_too_large")

        continuation = {
            "next_stage": policy["recommended_next_stage"],
            "operation": dispatched.operation,
            "idempotency_key": dispatched.intent["idempotency_key"],
            "policy_digest_sha256": policy["policy_digest_sha256"],
            "approval_id": dispatched.intent["approval"]["approval_id"],
            "permission_snapshot_digest": dispatched.intent["permission_snapshot_digest"],
            "handler_result_sha256": hashlib.sha256(encoded_result).hexdigest(),
            "handler_result": handler_result,
        }
        consume = getattr(context, "checkpoint_council_resume_consumed", None)
        if not callable(consume):
            return TaskExecutionResult("blocked", "council_executor_checkpoint_api_missing")
        try:
            persisted = consume(continuation)
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "council_executor_checkpoint_rejected")
        except Exception:
            return TaskExecutionResult("retry", "council_executor_checkpoint_unavailable", 90)
        if persisted is not True:
            return TaskExecutionResult("retry", "council_executor_checkpoint_failed", 90)
        return TaskExecutionResult("completed")

    return continue_parent
