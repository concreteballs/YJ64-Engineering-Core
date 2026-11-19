"""Generic, model-agnostic parent-task resume checkpoint helpers.

The durable event is stored by the task store; this module validates and builds
its checkpoint representation. Child output remains untrusted evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .checkpoints import create_checkpoint, verify_checkpoint

PARENT_RESUME_PROTOCOL = "yj64.parent-resume.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_child_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the minimal immutable identity envelope for a child result."""
    if not isinstance(payload, Mapping):
        raise ValueError("child_result_must_be_object")
    data = dict(payload)
    if data.get("protocol_version") != PARENT_RESUME_PROTOCOL:
        raise ValueError("unsupported_parent_resume_protocol")
    parent_id = data.get("parent_task_id")
    child_id = data.get("child_task_id")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 1
           for value in (parent_id, child_id)):
        raise ValueError("invalid_parent_or_child_task_id")
    for key in ("correlation_key", "result_artifact_ref"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 1024:
            raise ValueError(f"invalid_{key}")
    if len(data["correlation_key"]) > 256:
        raise ValueError("invalid_correlation_key")
    if "?" in data["result_artifact_ref"] or "#" in data["result_artifact_ref"]:
        raise ValueError("artifact_reference_must_be_opaque")
    digest = data.get("result_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("invalid_result_sha256")
    if data.get("result_status") not in {"completed", "blocked", "failed", "cancelled"}:
        raise ValueError("invalid_result_status")
    if data.get("result_is_untrusted_data") is not True:
        raise ValueError("child_result_must_be_marked_untrusted")
    return data


def fetch_child_result_artifact(
    resume: Mapping[str, Any], artifact_store: Any,
) -> dict[str, Any]:
    """Fetch and integrity-check a completed child artifact; never trust its contents.

    Domain-specific parent handlers must still validate the returned JSON against
    their own schema and treat every field as untrusted input.
    """
    if not isinstance(resume, Mapping):
        raise ValueError("parent_resume_must_be_object")
    if resume.get("result_status") != "completed":
        raise ValueError("child_result_is_not_completed")
    reference = resume.get("result_artifact_ref")
    digest = resume.get("result_sha256")
    if not isinstance(reference, str) or not reference.strip() or "?" in reference or "#" in reference:
        raise ValueError("invalid_result_artifact_ref")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("invalid_result_sha256")
    getter = getattr(artifact_store, "get", None)
    if not callable(getter):
        raise TypeError("artifact_store_must_implement_get")
    content = getter(reference)
    if not isinstance(content, bytes) or not content:
        raise ValueError("child_result_artifact_must_be_nonempty_bytes")
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("child_result_artifact_sha256_mismatch")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("child_result_artifact_is_not_valid_json") from None
    if not isinstance(payload, dict):
        raise ValueError("child_result_artifact_must_be_json_object")
    return payload


def build_parent_resume_checkpoint(
    parent_checkpoint: Mapping[str, Any],
    child_result: Mapping[str, Any],
    *,
    resume_event_id: int,
) -> dict[str, Any]:
    """Create the next parent checkpoint without changing its authority state."""
    verify_checkpoint(parent_checkpoint)
    result = validate_child_result(child_result)
    parent_id = int(parent_checkpoint["task_id"])
    if result["parent_task_id"] != parent_id:
        raise ValueError("child_result_parent_identity_mismatch")
    if not isinstance(resume_event_id, int) or isinstance(resume_event_id, bool) or resume_event_id < 1:
        raise ValueError("invalid_resume_event_id")

    state = parent_checkpoint.get("task_state")
    if not isinstance(state, dict) or state.get("stage") != "waiting_child":
        raise ValueError("parent_task_is_not_waiting_for_child")
    if (
        state.get("expected_child_correlation_key") != result["correlation_key"]
        or state.get("expected_child_protocol_version") != result["protocol_version"]
    ):
        raise ValueError("child_result_does_not_match_parent_wait")

    resumed_state = dict(state)
    resumed_state["stage"] = "parent_resume_ready"
    resumed_state["child_resume"] = {
        "resume_event_id": resume_event_id,
        "protocol_version": result["protocol_version"],
        "correlation_key": result["correlation_key"],
        "child_task_id": result["child_task_id"],
        "result_artifact_ref": result["result_artifact_ref"],
        "result_sha256": result["result_sha256"],
        "result_status": result["result_status"],
        "result_is_untrusted_data": True,
    }
    artifact_refs = parent_checkpoint.get("artifact_refs", [])
    if not isinstance(artifact_refs, list) or any(not isinstance(x, str) for x in artifact_refs):
        raise ValueError("invalid_parent_artifact_refs")
    next_artifacts = list(artifact_refs)
    if result["result_artifact_ref"] not in next_artifacts:
        next_artifacts.append(result["result_artifact_ref"])
    return create_checkpoint(
        task_id=str(parent_id),
        sequence=parent_checkpoint["sequence"] + 1,
        state="checkpointed",
        task_spec_version=parent_checkpoint["task_spec_version"],
        task_state=resumed_state,
        budgets=parent_checkpoint.get("budgets", {}),
        approvals=parent_checkpoint.get("approvals", {}),
        artifact_refs=next_artifacts,
        previous_checkpoint_hash=parent_checkpoint["checkpoint_hash"],
    )


def validate_parent_resume_checkpoint(
    checkpoint: Mapping[str, Any], *, parent_task_id: int,
) -> dict[str, Any]:
    """Verify a resumed parent checkpoint before exposing the child result."""
    verify_checkpoint(checkpoint)
    if checkpoint.get("task_id") != str(parent_task_id):
        raise ValueError("parent_resume_checkpoint_identity_mismatch")
    state = checkpoint.get("task_state")
    resume = state.get("child_resume") if isinstance(state, dict) else None
    if not isinstance(state, dict) or state.get("stage") != "parent_resume_ready" or not isinstance(resume, dict):
        raise ValueError("parent_resume_checkpoint_not_ready")
    if (
        not isinstance(resume.get("resume_event_id"), int)
        or isinstance(resume.get("resume_event_id"), bool)
        or resume["resume_event_id"] < 1
        or not isinstance(resume.get("child_task_id"), int)
        or isinstance(resume.get("child_task_id"), bool)
        or resume["child_task_id"] < 1
        or resume.get("result_is_untrusted_data") is not True
    ):
        raise ValueError("parent_resume_checkpoint_identity_invalid")
    return {
        **resume,
        "parent_task_id": parent_task_id,
        "parent_task_state": {
            key: value for key, value in state.items() if key != "child_resume"
        },
    }
