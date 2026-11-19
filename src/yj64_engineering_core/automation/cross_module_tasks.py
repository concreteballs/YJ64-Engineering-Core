"""Durable cross-discipline task handler for the existing WorkerRunner.

The handler is injected into the existing WorkerRunner handler map. It does not
create a worker, queue, registry, plugin loader, or grant execution permissions.
Specialist adapters are explicitly supplied by the host application.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from ..cross_module import (
    ConditionDisposition,
    evaluate_cross_module_acceptance,
)
from ..extensions import CapabilityRequirement, ExtensionRegistry
from .checkpoints import create_checkpoint, verify_checkpoint
from .worker import TaskExecutionResult

TASK_TYPE = "cross_module_assessment"
PROTOCOL_VERSION = "yj64.cross_module.task.v1"


def _json_object(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise ValueError(f"invalid_{label}") from None
    if not isinstance(value, dict):
        raise ValueError(f"invalid_{label}")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _checkpoint(context: Any, state: dict[str, Any]) -> bool:
    # Detach nested mutable objects before hashing; adapters may still hold references.
    state_snapshot = json.loads(json.dumps(state, sort_keys=True, ensure_ascii=False, allow_nan=False))
    previous = context.load_latest_checkpoint()
    if previous is not None:
        verify_checkpoint(previous)
        if previous.get("task_id") != str(context.task_id):
            raise ValueError("checkpoint_identity_mismatch")
        previous_state = previous.get("task_state")
        if not isinstance(previous_state, dict):
            raise ValueError("invalid_checkpoint_state")
        sequence = previous["sequence"] + 1
        previous_hash = previous["checkpoint_hash"]
        task_spec_version = previous["task_spec_version"]
        budgets = previous.get("budgets", {})
        approvals = previous.get("approvals", {})
        artifact_refs = previous.get("artifact_refs", [])
    else:
        sequence, previous_hash = 1, None
        task_spec_version = PROTOCOL_VERSION
        budgets, approvals, artifact_refs = {}, {}, []
    checkpoint = create_checkpoint(
        task_id=str(context.task_id),
        sequence=sequence,
        state="checkpointed",
        task_spec_version=task_spec_version,
        task_state=state_snapshot,
        budgets=budgets,
        approvals=approvals,
        artifact_refs=artifact_refs,
        previous_checkpoint_hash=previous_hash,
    )
    return bool(context.save_checkpoint(checkpoint))


def _handoff_assessment(
    payload: Mapping[str, Any], context: Any, candidate_digest: str,
    assessment: Mapping[str, Any], artifact_store_factory: Any,
) -> bool:
    parent_task_id = payload.get("parent_task_id")
    correlation_key = payload.get("correlation_key")
    parent_protocol = payload.get("parent_resume_protocol_version")
    if all(value is None for value in (parent_task_id, correlation_key, parent_protocol)):
        return True
    from .parent_resume import PARENT_RESUME_PROTOCOL
    if (
        not isinstance(parent_task_id, int) or isinstance(parent_task_id, bool) or parent_task_id < 1
        or not isinstance(correlation_key, str) or not correlation_key.strip() or len(correlation_key) > 256
        or parent_protocol != PARENT_RESUME_PROTOCOL
    ):
        raise ValueError("cross_module_parent_handoff_invalid")
    artifact = json.dumps({
        "schema_id": "yj64.cross_module.assessment-artifact.v1",
        "schema_version": "1.0",
        "candidate_digest": candidate_digest,
        "assessment": assessment,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(artifact).hexdigest()
    if artifact_store_factory is not None:
        artifact_store = artifact_store_factory()
    else:
        from .supabase_storage import SupabaseStorageArtifactStore
        artifact_store = SupabaseStorageArtifactStore.from_environment()
    artifact_ref = artifact_store.put(
        namespace=f"cross-module/{context.task_id}/{candidate_digest}",
        content=artifact,
        content_type="application/json",
    )
    if not isinstance(artifact_ref, str) or not artifact_ref.strip() or "?" in artifact_ref or "#" in artifact_ref:
        raise ValueError("cross_module_artifact_reference_invalid")
    child_result = {
        "protocol_version": PARENT_RESUME_PROTOCOL,
        "parent_task_id": parent_task_id,
        "child_task_id": context.task_id,
        "correlation_key": correlation_key,
        "result_artifact_ref": artifact_ref,
        "result_sha256": digest,
        "result_status": "completed",
        "result_is_untrusted_data": True,
    }
    handoff = context.record_parent_resume_event(parent_task_id, child_result)
    return isinstance(handoff, dict) and handoff.get("accepted") is True


def enqueue_cross_module_assessment_from_parent(
    context: Any,
    candidate: Mapping[str, Any],
    relevant_modules: list[str],
    *,
    max_attempts: int = 5,
) -> TaskExecutionResult:
    """Enqueue one idempotent child assessment and suspend its parent task.

    The parent checkpoint is written before its lease is released. If enqueue
    succeeds but suspension fails, retrying uses the same dedupe key.
    """
    from .parent_resume import PARENT_RESUME_PROTOCOL
    try:
        if not isinstance(candidate, Mapping) or not isinstance(relevant_modules, list) or not relevant_modules:
            return TaskExecutionResult("blocked", "cross_module_parent_input_invalid")
        if any(not isinstance(module, str) or not module.strip() for module in relevant_modules):
            return TaskExecutionResult("blocked", "cross_module_parent_scope_invalid")
        if len(set(relevant_modules)) != len(relevant_modules):
            return TaskExecutionResult("blocked", "cross_module_parent_scope_invalid")
        candidate_data = dict(candidate)
        candidate_digest = _digest(candidate_data)
        candidate_id = candidate_data.get("candidate_id")
        version = candidate_data.get("version")
        if not isinstance(candidate_id, str) or not candidate_id.strip() or not isinstance(version, int) or isinstance(version, bool) or version < 1:
            return TaskExecutionResult("blocked", "cross_module_parent_candidate_identity_invalid")
        correlation_key = f"cross-module:{context.task_id}:{candidate_id}:{version}:{candidate_digest}"
        if len(correlation_key) > 256:
            return TaskExecutionResult("blocked", "cross_module_parent_correlation_key_too_long")
        payload = {
            "protocol_version": PROTOCOL_VERSION,
            "candidate": candidate_data,
            "relevant_modules": sorted(relevant_modules),
            "parent_task_id": context.task_id,
            "correlation_key": correlation_key,
            "parent_resume_protocol_version": PARENT_RESUME_PROTOCOL,
        }
        queued = context.store.enqueue_task(
            TASK_TYPE, payload,
            dedupe_key=f"cross-module-parent:{context.task_id}:{candidate_digest}",
            max_attempts=max_attempts,
        )
        if not isinstance(queued, dict) or not (queued.get("enqueued") or queued.get("duplicate")):
            return TaskExecutionResult("retry", "cross_module_child_enqueue_failed", 90)

        previous = context.load_latest_checkpoint()
        if previous is not None:
            verify_checkpoint(previous)
            if previous.get("task_id") != str(context.task_id):
                return TaskExecutionResult("blocked", "cross_module_parent_checkpoint_identity_mismatch")
            previous_state = previous.get("task_state")
            if not isinstance(previous_state, dict):
                return TaskExecutionResult("blocked", "cross_module_parent_checkpoint_invalid")
            task_state = dict(previous_state)
            if task_state.get("stage") == "waiting_child":
                if (
                    task_state.get("expected_child_correlation_key") != correlation_key
                    or task_state.get("expected_child_protocol_version") != PARENT_RESUME_PROTOCOL
                ):
                    return TaskExecutionResult("blocked", "cross_module_parent_wait_conflict")
            else:
                task_state["stage_before_child"] = task_state.get("stage")
            sequence = previous["sequence"] + 1
            previous_hash = previous["checkpoint_hash"]
            task_spec_version = previous["task_spec_version"]
            budgets, approvals = previous.get("budgets", {}), previous.get("approvals", {})
            artifacts = previous.get("artifact_refs", [])
        else:
            task_state, sequence, previous_hash = {}, 1, None
            task_spec_version, budgets, approvals, artifacts = PROTOCOL_VERSION, {}, {}, []
        task_state.update({
            "stage": "waiting_child",
            "expected_child_correlation_key": correlation_key,
            "expected_child_protocol_version": PARENT_RESUME_PROTOCOL,
            "child_task_type": TASK_TYPE,
            "child_candidate_digest": candidate_digest,
        })
        checkpoint = create_checkpoint(
            task_id=str(context.task_id), sequence=sequence, state="checkpointed",
            task_spec_version=task_spec_version, task_state=task_state,
            budgets=budgets, approvals=approvals, artifact_refs=artifacts,
            previous_checkpoint_hash=previous_hash,
        )
        if not context.suspend_for_child(checkpoint, correlation_key, PARENT_RESUME_PROTOCOL):
            return TaskExecutionResult("retry", "cross_module_parent_suspend_failed", 90)
        return TaskExecutionResult("suspended")
    except (TypeError, ValueError):
        return TaskExecutionResult("blocked", "cross_module_parent_invalid_state")
    except Exception:
        return TaskExecutionResult("retry", "cross_module_parent_orchestration_failed", 90)


def create_cross_module_task_handler(
    *,
    registry: ExtensionRegistry,
    module_bindings: Mapping[str, str],
    adapters: Mapping[str, Any],
    disposition_provider: Any = None,
    artifact_store_factory: Any = None,
):
    """Create a TaskHandler to register under TASK_TYPE in the existing worker.

    module_bindings maps canonical reviewer_module IDs to registered extension
    IDs. adapters maps extension IDs to host-created objects implementing
    review_candidate(candidate) and contribute_enhancements(candidate).
    """
    if not isinstance(registry, ExtensionRegistry):
        raise TypeError("registry must be the existing ExtensionRegistry")
    if not isinstance(module_bindings, Mapping) or not module_bindings:
        raise ValueError("module_bindings is required")
    if not isinstance(adapters, Mapping):
        raise ValueError("adapters must be a mapping")
    if len(set(module_bindings.values())) != len(module_bindings):
        raise ValueError("each discipline must have a distinct extension binding")
    if disposition_provider is not None and not callable(disposition_provider):
        raise ValueError("disposition_provider must be callable")
    if artifact_store_factory is not None and not callable(artifact_store_factory):
        raise ValueError("artifact_store_factory must be callable")

    def handler(task: dict, context: Any) -> TaskExecutionResult:
        try:
            payload = _json_object(task.get("payload"), "task_payload")
            if payload.get("protocol_version") != PROTOCOL_VERSION:
                return TaskExecutionResult("blocked", "cross_module_protocol_unsupported")
            candidate = payload.get("candidate")
            if (not isinstance(candidate, dict)
                    or candidate.get("schema_id") != "yj64.cross_module.candidate.v1"
                    or candidate.get("schema_version") != "1.0"):
                return TaskExecutionResult("blocked", "cross_module_candidate_invalid")
            modules = payload.get("relevant_modules")
            if (not isinstance(modules, list) or not modules
                    or any(not isinstance(x, str) or not x.strip() for x in modules)
                    or len(set(modules)) != len(modules)):
                return TaskExecutionResult("blocked", "cross_module_scope_invalid")
            origin = candidate.get("origin_module")
            if origin not in modules:
                return TaskExecutionResult("blocked", "cross_module_origin_out_of_scope")
            if any(module not in module_bindings for module in modules):
                return TaskExecutionResult("blocked", "cross_module_binding_missing")

            bindings = {module: module_bindings[module] for module in modules}
            for module, extension_id in bindings.items():
                manifest = registry.get(extension_id)
                if manifest.kind != "discipline_pack" or manifest.permissions:
                    return TaskExecutionResult("blocked", "cross_module_manifest_not_permitted")
                if extension_id not in adapters:
                    return TaskExecutionResult("blocked", "cross_module_adapter_unavailable")
                for operation, output_schema in (
                    ("review_candidate", "yj64.cross_module.review.v1"),
                    ("contribute_enhancements", "yj64.cross_module.contribution.v1"),
                ):
                    matches = registry.find_compatible(CapabilityRequirement(
                        operation=operation,
                        input_schema="yj64.cross_module.candidate.v1",
                        output_schema=output_schema,
                    ))
                    if manifest not in matches:
                        return TaskExecutionResult("blocked", "cross_module_capability_mismatch")

            candidate_digest = _digest(candidate)
            previous = context.load_latest_checkpoint()
            saved = {}
            if previous is not None:
                verify_checkpoint(previous)
                state = previous.get("task_state", {})
                if isinstance(state, dict) and state.get("stage") == "cross_module_assessment_ready":
                    if state.get("candidate_digest") != candidate_digest:
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_candidate_mismatch")
                    if state.get("relevant_modules") != sorted(modules):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_scope_mismatch")
                    assessment = state.get("assessment")
                    if not isinstance(assessment, dict):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_invalid")
                    try:
                        if not _handoff_assessment(payload, context, candidate_digest, assessment, artifact_store_factory):
                            return TaskExecutionResult("retry", "cross_module_parent_handoff_pending", 90)
                    except Exception:
                        return TaskExecutionResult("retry", "cross_module_parent_handoff_failed", 90)
                    return TaskExecutionResult("completed")
                if isinstance(state, dict) and state.get("stage") == "cross_module_assessment":
                    if state.get("candidate_digest") != candidate_digest:
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_candidate_mismatch")
                    if state.get("relevant_modules") != sorted(modules):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_scope_mismatch")
                    saved = state.get("module_outputs", {})
                    if not isinstance(saved, dict):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_invalid")
                    saved = json.loads(json.dumps(saved, sort_keys=True, ensure_ascii=False, allow_nan=False))

            reviews, contributions = [], []
            for module in sorted(modules):
                extension_id = bindings[module]
                adapter = adapters[extension_id]
                output = saved.get(module, {})
                if not isinstance(output, dict):
                    return TaskExecutionResult("blocked", "cross_module_checkpoint_invalid")

                review = output.get("review")
                if review is None:
                    review = adapter.review_candidate(dict(candidate))
                    if not isinstance(review, dict):
                        return TaskExecutionResult("blocked", "cross_module_review_invalid")
                    if (review.get("reviewer_module") != module
                            or review.get("reviewer_version") != registry.get(extension_id).version
                            or review.get("candidate") != candidate
                            or review.get("schema_id") != "yj64.cross_module.review.v1"
                            or review.get("schema_version") != "1.0"):
                        return TaskExecutionResult("blocked", "cross_module_review_identity_mismatch")
                    output["review"] = review
                    saved[module] = output
                    state = {
                        "stage": "cross_module_assessment",
                        "candidate_digest": candidate_digest,
                        "candidate": candidate,
                        "relevant_modules": sorted(modules),
                        "module_outputs": saved,
                    }
                    if not _checkpoint(context, state):
                        return TaskExecutionResult("retry", "cross_module_checkpoint_failed", 90)

                contribution = output.get("contribution")
                if contribution is None:
                    contribution = adapter.contribute_enhancements(dict(candidate))
                    if not isinstance(contribution, dict):
                        return TaskExecutionResult("blocked", "cross_module_contribution_invalid")
                    if (contribution.get("module_id") != module
                            or contribution.get("candidate") != candidate
                            or contribution.get("schema_id") != "yj64.cross_module.contribution.v1"
                            or contribution.get("schema_version") != "1.0"):
                        return TaskExecutionResult("blocked", "cross_module_contribution_identity_mismatch")
                    output["contribution"] = contribution
                    saved[module] = output
                    state = {
                        "stage": "cross_module_assessment",
                        "candidate_digest": candidate_digest,
                        "candidate": candidate,
                        "relevant_modules": sorted(modules),
                        "module_outputs": saved,
                    }
                    if not _checkpoint(context, state):
                        return TaskExecutionResult("retry", "cross_module_checkpoint_failed", 90)
                reviews.append(review)
                contributions.append(contribution)

            dispositions = ()
            if disposition_provider is not None:
                supplied = disposition_provider(dict(candidate), tuple(reviews), context)
                if not isinstance(supplied, (list, tuple)) or any(
                    not isinstance(item, ConditionDisposition) for item in supplied
                ):
                    return TaskExecutionResult("blocked", "cross_module_disposition_invalid")
                dispositions = tuple(supplied)
            assessment = evaluate_cross_module_acceptance(
                candidate, modules, reviews, contributions, dispositions
            )
            final_state = {
                "stage": "cross_module_assessment_ready",
                "candidate_digest": candidate_digest,
                "candidate": candidate,
                "relevant_modules": sorted(modules),
                "module_outputs": saved,
                "assessment": assessment,
            }
            if not _checkpoint(context, final_state):
                return TaskExecutionResult("retry", "cross_module_checkpoint_failed", 90)

            # Parent handoff is opt-in per task payload. Artifact storage is
            # content-addressed and the parent event is idempotent, so retries
            # can safely repeat this publication after a checkpointed result.
            try:
                if not _handoff_assessment(payload, context, candidate_digest, assessment, artifact_store_factory):
                    return TaskExecutionResult("retry", "cross_module_parent_handoff_pending", 90)
            except ValueError as exc:
                if str(exc) == "cross_module_parent_handoff_invalid":
                    return TaskExecutionResult("blocked", "cross_module_parent_handoff_invalid")
                return TaskExecutionResult("retry", "cross_module_parent_handoff_failed", 90)
            except Exception:
                return TaskExecutionResult("retry", "cross_module_parent_handoff_failed", 90)

            # Completing this queue item means assessment computation finished;
            # it does not mean the candidate was accepted.
            return TaskExecutionResult("completed")
        except KeyError:
            return TaskExecutionResult("blocked", "cross_module_required_field_missing")
        except TypeError:
            return TaskExecutionResult("blocked", "cross_module_invalid_type")
        except ValueError as exc:
            import re
            detail = re.sub(r"[^a-z0-9]+", "_", str(exc).lower()).strip("_")[:72]
            return TaskExecutionResult("blocked", "cross_module_invalid_value_" + (detail or "unspecified"))
        except Exception:
            return TaskExecutionResult("retry", "cross_module_adapter_error", 90)

    return handler
