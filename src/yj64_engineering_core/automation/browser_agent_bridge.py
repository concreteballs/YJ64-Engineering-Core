"""Validation primitives for the versioned browser-agent bridge envelopes.

These are transport contracts only: they do not send browser commands or trust
agent assertions as CI/task completion evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Mapping

SCHEMA_VERSION = "yj64.browser-agent-envelope.v1"
EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
EXPECTED_BRANCH = "main"
MESSAGE_TYPES = {
    "ci_observation", "test_report", "verification_request",
    "verification_response", "council_request", "council_result",
    "blocked_notice", "cycle_complete",
}
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_COMMIT_SHA = re.compile(r"^[a-f0-9]{40}$")
_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("message content must be finite JSON data") from exc


def payload_hash(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    return hashlib.sha256(_canonical_json(dict(payload))).hexdigest()



def create_envelope(
    *,
    message_type: str,
    task_id: int | str,
    idempotency_key: str,
    payload: Mapping[str, Any],
    ttl_seconds: int = 3600,
    run_id: int | None = None,
    run_attempt: int | None = None,
    commit_sha: str | None = None,
    now: datetime | None = None,
    message_id: str | None = None,
) -> dict:
    """Create a signed-by-hash, scope-bound envelope for an existing agent channel.

    The payload hash protects integrity, not sender identity. Authentication and
    authorization must still be enforced by the receiving service.
    """
    if message_type not in MESSAGE_TYPES:
        raise ValueError("unsupported message type")
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 256:
        raise ValueError("idempotency_key must be 8-256 characters")
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 2592000:
        raise ValueError("ttl_seconds must be between 1 and 2592000")
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "message_id": message_id or uuid.uuid4().hex,
        "message_type": message_type,
        "created_at": current.isoformat().replace("+00:00", "Z"),
        "expires_at": (current + timedelta(seconds=ttl_seconds)).isoformat().replace("+00:00", "Z"),
        "repository": EXPECTED_REPOSITORY,
        "branch": EXPECTED_BRANCH,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
        "payload_sha256": payload_hash(payload),
        "payload": dict(payload),
    }
    if run_id is not None:
        envelope["run_id"] = run_id
    if run_attempt is not None:
        envelope["run_attempt"] = run_attempt
    if commit_sha is not None:
        envelope["commit_sha"] = commit_sha
    return validate_envelope(envelope, now=current)

def validate_envelope(envelope: Mapping[str, Any], *, now: datetime | None = None) -> dict:
    """Validate scope, identity, lifecycle timestamps and payload integrity."""
    if not isinstance(envelope, Mapping):
        raise ValueError("envelope must be an object")
    data = dict(envelope)
    allowed = {
        "schema_version", "message_id", "message_type", "created_at", "expires_at",
        "repository", "branch", "task_id", "run_id", "run_attempt", "commit_sha",
        "payload_sha256", "idempotency_key", "payload",
    }
    if set(data) - allowed:
        raise ValueError("envelope contains unknown fields")
    required = {
        "schema_version", "message_id", "message_type", "created_at",
        "expires_at", "repository", "branch", "task_id", "idempotency_key", "payload_sha256", "payload",
    }
    if not required.issubset(data):
        raise ValueError("envelope is missing required fields")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported envelope schema")
    if data.get("message_type") not in MESSAGE_TYPES:
        raise ValueError("unsupported message type")
    if data.get("repository") != EXPECTED_REPOSITORY or data.get("branch") != EXPECTED_BRANCH:
        raise ValueError("message scope is not authorized")
    if not isinstance(data.get("message_id"), str) or not _ID.fullmatch(data["message_id"]):
        raise ValueError("message_id must be a safe 8-128 character identifier")
    task_id = data.get("task_id")
    if isinstance(task_id, bool) or not (
        (isinstance(task_id, int) and task_id >= 1)
        or (isinstance(task_id, str) and task_id.strip() and len(task_id) <= 128)
    ):
        raise ValueError("task_id must be a positive integer or non-empty string")

    for key in ("run_id", "run_attempt"):
        if key in data and data[key] is not None and (
            not isinstance(data[key], int) or isinstance(data[key], bool) or data[key] < 1
        ):
            raise ValueError(f"{key} must be a positive integer")
    if "run_attempt" in data and "run_id" not in data:
        raise ValueError("run_attempt requires run_id")
    if "commit_sha" in data and data["commit_sha"] is not None and (
        not isinstance(data["commit_sha"], str) or not _COMMIT_SHA.fullmatch(data["commit_sha"])
    ):
        raise ValueError("commit_sha must be a lowercase 40-character SHA")
    if not isinstance(data.get("idempotency_key"), str) or not 8 <= len(data["idempotency_key"]) <= 256:
        raise ValueError("idempotency_key must be 8-256 characters")
    if not isinstance(data["payload"], Mapping):
        raise ValueError("payload must be an object")
    for stamp in ("created_at", "expires_at"):
        value = data[stamp]
        if not isinstance(value, str):
            raise ValueError(f"{stamp} must be an ISO timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{stamp} must be an ISO timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError(f"{stamp} must include timezone")
        data[stamp] = parsed.astimezone(timezone.utc)
    if data["expires_at"] <= data["created_at"]:
        raise ValueError("expires_at must be after created_at")
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if data["expires_at"] <= current.astimezone(timezone.utc):
        raise ValueError("message has expired")
    supplied = data["payload_sha256"]
    if not isinstance(supplied, str) or not _SHA256.fullmatch(supplied):
        raise ValueError("payload_sha256 must be lowercase SHA-256")
    if supplied != payload_hash(data["payload"]):
        raise ValueError("payload hash mismatch")
    data["created_at"] = data["created_at"].isoformat().replace("+00:00", "Z")
    data["expires_at"] = data["expires_at"].isoformat().replace("+00:00", "Z")
    return data
