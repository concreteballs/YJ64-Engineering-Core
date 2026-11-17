"""Canonical, integrity-checked durable task checkpoint contract.

This module is deliberately storage-agnostic. A checkpoint is a bounded snapshot
of authoritative task state; it is not a model transcript or a live session.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping


SCHEMA_VERSION = "yj64.task-checkpoint.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STATES = {
    "queued", "leased", "running", "checkpointed", "completed",
    "blocked", "paused", "cancelled", "failed",
}


def _canonical_json(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint data must be finite JSON-compatible data") from exc
    return encoded.encode("utf-8")


def _require_mapping(name: str, value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    result = dict(value)
    _canonical_json(result)
    return result


def create_checkpoint(
    *,
    task_id: str,
    sequence: int,
    state: str,
    task_spec_version: str,
    task_state: Mapping[str, Any],
    budgets: Mapping[str, Any],
    approvals: Mapping[str, Any],
    artifact_refs: list[str] | tuple[str, ...] = (),
    previous_checkpoint_hash: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a canonical checkpoint and attach its SHA-256 integrity hash."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id is required")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    if not isinstance(state, str) or state not in _STATES:
        raise ValueError("unsupported task state")
    if not isinstance(task_spec_version, str) or not task_spec_version.strip():
        raise ValueError("task_spec_version is required")
    if previous_checkpoint_hash is not None and (
        not isinstance(previous_checkpoint_hash, str)
        or not _SHA256_RE.fullmatch(previous_checkpoint_hash)
    ):
        raise ValueError("previous_checkpoint_hash must be a lowercase SHA-256 hash")
    if not isinstance(artifact_refs, (list, tuple)) or any(
        not isinstance(ref, str) or not ref.strip() for ref in artifact_refs
    ):
        raise ValueError("artifact_refs must contain non-empty strings")

    timestamp = created_at or datetime.now(timezone.utc)
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)

    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "sequence": sequence,
        "state": state,
        "task_spec_version": task_spec_version,
        "created_at": timestamp.isoformat().replace("+00:00", "Z"),
        "task_state": _require_mapping("task_state", task_state),
        "budgets": _require_mapping("budgets", budgets),
        "approvals": _require_mapping("approvals", approvals),
        "artifact_refs": list(artifact_refs),
        "previous_checkpoint_hash": previous_checkpoint_hash,
    }
    checkpoint["checkpoint_hash"] = hashlib.sha256(
        _canonical_json(checkpoint)
    ).hexdigest()
    return checkpoint


def verify_checkpoint(checkpoint: Mapping[str, Any]) -> bool:
    """Verify schema identity and content hash without modifying the input."""
    if not isinstance(checkpoint, Mapping):
        raise ValueError("checkpoint must be an object")
    data = dict(checkpoint)
    supplied_hash = data.pop("checkpoint_hash", None)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported checkpoint schema")
    if not isinstance(supplied_hash, str) or not _SHA256_RE.fullmatch(supplied_hash):
        raise ValueError("checkpoint_hash must be a lowercase SHA-256 hash")
    expected_hash = hashlib.sha256(_canonical_json(data)).hexdigest()
    if not hmac.compare_digest(supplied_hash, expected_hash):
        raise ValueError("checkpoint integrity check failed")
    return True
