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
    ConditionStatus,
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
        task_state=state,
        budgets=budgets,
        approvals=approvals,
        artifact_refs=artifact_refs,
        previous_checkpoint_hash=previous_hash,
    )
    return bool(context.save_checkpoint(checkpoint))


def _condition_dispositions(values: Any) -> tuple[ConditionDisposition, ...]:
    if values is None:
        return ()
    if not isinstance(values, list):
        raise ValueError("invalid_condition_dispositions")
    result = []
    for item in values:
        if not isinstance(item, dict):
            raise ValueError("invalid_condition_disposition")
        result.append(ConditionDisposition(
            candidate=item.get("candidate"),
            reviewer_module=item.get("reviewer_module"),
            condition_id=item.get("condition_id"),
            condition_text=item.get("condition_text"),
            status=ConditionStatus(item.get("status")),
            rationale=item.get("rationale"),
            decided_by=item.get("decided_by"),
            decision_version=item.get("decision_version"),
            evidence=tuple(item.get("evidence", ())),
        ))
    return tuple(result)


def create_cross_module_task_handler(
    *,
    registry: ExtensionRegistry,
    module_bindings: Mapping[str, str],
    adapters: Mapping[str, Any],
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

    def handler(task: dict, context: Any) -> TaskExecutionResult:
        try:
            payload = _json_object(task.get("payload"), "task_payload")
            if payload.get("protocol_version") != PROTOCOL_VERSION:
                return TaskExecutionResult("blocked", "cross_module_protocol_unsupported")
            candidate = payload.get("candidate")
            if not isinstance(candidate, dict):
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
                if isinstance(state, dict) and state.get("stage") == "cross_module_assessment":
                    if state.get("candidate_digest") != candidate_digest:
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_candidate_mismatch")
                    if state.get("relevant_modules") != sorted(modules):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_scope_mismatch")
                    saved = state.get("module_outputs", {})
                    if not isinstance(saved, dict):
                        return TaskExecutionResult("blocked", "cross_module_checkpoint_invalid")

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
                            or review.get("schema_id") != "yj64.cross_module.review.v1"\n                            or review.get("schema_version") != "1.0"):
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
                            or contribution.get("schema_id") != "yj64.cross_module.contribution.v1"\n                            or contribution.get("schema_version") != "1.0"):
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

            dispositions = _condition_dispositions(payload.get("condition_dispositions"))
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
            # Completing this queue item means assessment computation finished;
            # it does not mean the candidate was accepted.
            return TaskExecutionResult("completed")
        except (KeyError, TypeError, ValueError):
            return TaskExecutionResult("blocked", "cross_module_invalid_task")
        except Exception:
            return TaskExecutionResult("retry", "cross_module_adapter_error", 90)

    return handler
