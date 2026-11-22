"""Fail-closed approval gate for typed engineering executor intents.

This module does not execute tools, shell commands, or repository operations.
It converts a validated advisory Council policy plus an externally verified,
task-scoped approval into a bounded request for an existing domain handler.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Callable, Mapping

SCHEMA_VERSION = "yj64.executor-intent.v1"

_STAGE_OPERATIONS = {
    "resolve_conflict": "engineering.resolve_conflict",
    "collect_independent_evidence": "engineering.collect_evidence",
    "human_review": "engineering.human_review",
    "independent_domain_validation": "engineering.validate_domain",
}
_POLICY_KEYS = {
    "schema_version", "source", "input_digest_sha256", "recommended_next_stage",
    "claim_checks", "review_flags", "rationale_codes", "authority",
    "execution_allowed", "requires_human_approval", "permission_changes",
    "executable_actions", "policy_digest_sha256",
}
_APPROVAL_KEYS = {
    "approval_id", "issuer", "approved_at", "task_id",
    "policy_digest_sha256", "permission_snapshot_digest", "operation", "scope", "signature",
}


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("executor_intent_requires_finite_json") from None


def _nonempty(value: Any, name: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"executor_{name}_invalid")
    return value.strip()


def _timestamp(value: Any) -> str:
    text = _nonempty(value, "approval_timestamp", 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("executor_approval_timestamp_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("executor_approval_timestamp_must_be_timezone_aware")
    return parsed.isoformat().replace("+00:00", "Z")


def _verify_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ValueError("executor_policy_must_be_object")
    data = dict(policy)
    _canonical(data)
    if set(data) != _POLICY_KEYS:
        raise ValueError("executor_policy_has_unscoped_fields")
    if (
        data["schema_version"] != "yj64.council.decision-policy.v1"
        or data["authority"] != "advisory_only"
        or data["execution_allowed"] is not False
        or data["requires_human_approval"] is not True
        or data["permission_changes"] != []
        or data["executable_actions"] != []
    ):
        raise ValueError("executor_policy_authority_invalid")
    stage = data["recommended_next_stage"]
    if stage not in _STAGE_OPERATIONS:
        raise ValueError("executor_policy_stage_unsupported")
    supplied = data["policy_digest_sha256"]
    unsigned = dict(data)
    unsigned.pop("policy_digest_sha256")
    expected = hashlib.sha256(_canonical(unsigned)).hexdigest()
    if not isinstance(supplied, str) or supplied != expected:
        raise ValueError("executor_policy_digest_invalid")
    source = data["source"]
    if not isinstance(source, Mapping):
        raise ValueError("executor_policy_source_invalid")
    parent_id = source.get("parent_task_id")
    if not isinstance(parent_id, int) or isinstance(parent_id, bool) or parent_id < 1:
        raise ValueError("executor_policy_parent_identity_invalid")
    return data


def build_executor_intent(
    *,
    decision_policy: Mapping[str, Any],
    approval: Mapping[str, Any],
    task_id: str,
    permission_snapshot_digest: str,
    verify_approval: Callable[[Mapping[str, Any]], bool],
) -> dict[str, Any]:
    """Build a typed handler request only after external approval verification.

    The verifier must authenticate the issuer/signature and confirm that the
    approval is still valid against the authoritative permission snapshot.
    This function intentionally has no executor or command-running interface.
    """
    policy = _verify_policy(decision_policy)
    task = _nonempty(task_id, "task_id", 128)
    permission_digest = _nonempty(permission_snapshot_digest, "permission_snapshot_digest", 64)
    if len(permission_digest) != 64 or any(ch not in "0123456789abcdef" for ch in permission_digest):
        raise ValueError("executor_permission_snapshot_digest_invalid")
    if str(policy["source"]["parent_task_id"]) != task:
        raise ValueError("executor_policy_parent_task_mismatch")

    if not isinstance(approval, Mapping):
        raise ValueError("executor_approval_must_be_object")
    approved = dict(approval)
    _canonical(approved)
    if set(approved) != _APPROVAL_KEYS:
        raise ValueError("executor_approval_has_unscoped_fields")

    operation = _STAGE_OPERATIONS[policy["recommended_next_stage"]]
    if (
        _nonempty(approved["task_id"], "approval_task_id", 128) != task
        or _nonempty(approved["policy_digest_sha256"], "approval_policy_digest", 64)
        != policy["policy_digest_sha256"]
        or _nonempty(approved["operation"], "approval_operation", 128) != operation
        or _nonempty(approved["permission_snapshot_digest"], "approval_permission_digest", 64)
        != permission_digest
    ):
        raise ValueError("executor_approval_scope_mismatch")
    _nonempty(approved["approval_id"], "approval_id", 128)
    _nonempty(approved["issuer"], "approval_issuer", 128)
    _nonempty(approved["signature"], "approval_signature", 4096)
    approved_at = _timestamp(approved["approved_at"])
    if not isinstance(approved["scope"], Mapping):
        raise ValueError("executor_approval_scope_invalid")
    scope = dict(approved["scope"])
    if set(scope) - {"domain", "artifact_refs", "resource_ids"}:
        raise ValueError("executor_approval_scope_has_unscoped_fields")
    if "domain" in scope:
        _nonempty(scope["domain"], "approval_scope_domain", 128)
    for key in ("artifact_refs", "resource_ids"):
        if key in scope:
            values = scope[key]
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip() or len(item) > 1024
                for item in values
            ):
                raise ValueError(f"executor_approval_{key}_invalid")
    _canonical(scope)

    try:
        verified = verify_approval(approved)
    except Exception:
        raise ValueError("executor_approval_verification_failed") from None
    if verified is not True:
        raise ValueError("executor_approval_not_verified")

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task,
        "policy_digest_sha256": policy["policy_digest_sha256"],
        "operation": operation,
        "approval": {
            "approval_id": approved["approval_id"],
            "issuer": approved["issuer"],
            "approved_at": approved_at,
        },
        "permission_snapshot_digest": permission_digest,
        "scope": scope,
        "authority": "externally_approved_typed_handler_intent",
        "dispatch_allowed": True,
        "commands": [],
        "shell": None,
        "arbitrary_code": None,
    }
