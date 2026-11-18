"""Generic, versioned task envelope for the YJ64 orchestration layer.

This contract is deliberately separate from EngineeringRequest: it describes
work submitted to the coordinator, not the domain-specific input of a solver.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


TASK_CONTRACT_VERSION = "1.0"
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TASK_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_COUNCIL_POLICIES = {"never", "optional", "required"}
_MAX_ENVELOPE_BYTES = 262_144


def _validate_json_value(value: Any, path: str = "input") -> None:
    """Accept only bounded-shape JSON values and finite numbers."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{path} must not contain non-finite numbers")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} object keys must be strings")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contains unsupported type {type(value).__name__}")


@dataclass(frozen=True)
class TaskRequest:
    """Portable task envelope shared by API ingress, queue, and task handlers.

    Domain-specific payloads remain owned by their adapters/contracts. The
    coordinator uses task_type and requested_capabilities for explicit routing.
    """

    task_id: str
    task_type: str
    title: str
    objective: str
    input_data: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    requested_capabilities: tuple[str, ...] = ()
    council_policy: str = "optional"
    approval_policy: dict[str, Any] = field(default_factory=dict)
    contract_version: str = TASK_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("task_id", "title", "objective", "contract_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not _TASK_ID.fullmatch(self.task_id):
            raise ValueError("task_id contains unsupported characters")
        if not isinstance(self.task_type, str) or not _TASK_TYPE.fullmatch(self.task_type):
            raise ValueError("task_type must be a lowercase identifier")
        if self.contract_version != TASK_CONTRACT_VERSION:
            raise ValueError(f"Unsupported task contract version: {self.contract_version}")
        if self.council_policy not in _COUNCIL_POLICIES:
            raise ValueError("council_policy must be never, optional, or required")
        for name in ("input_data", "constraints", "approval_policy"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be an object")
            _validate_json_value(value, name)
        if not isinstance(self.requested_capabilities, (tuple, list)):
            raise TypeError("requested_capabilities must be a list or tuple")
        for capability in self.requested_capabilities:
            if not isinstance(capability, str) or not _CAPABILITY.fullmatch(capability):
                raise ValueError("requested_capabilities contains an invalid capability")
        encoded = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > _MAX_ENVELOPE_BYTES:
            raise ValueError("task request exceeds the 256 KiB envelope limit")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, allow_nan=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRequest":
        if not isinstance(data, dict):
            raise TypeError("Task request must be a JSON object")
        payload = dict(data)
        if "requested_capabilities" in payload:
            payload["requested_capabilities"] = tuple(payload["requested_capabilities"])
        return cls(**payload)

    @classmethod
    def from_json(cls, source: str) -> "TaskRequest":
        try:
            data = json.loads(
                source,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    ValueError(f"Invalid JSON numeric constant: {token}")
                ),
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid task request JSON: {exc}") from exc
        return cls.from_dict(data)
