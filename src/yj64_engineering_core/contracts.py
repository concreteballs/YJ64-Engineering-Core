"""Versioned, JSON-safe engineering request and response contracts.

The contract layer is intentionally independent of CAD and physics engines.
All physical quantities use SI units. This module validates data at the
boundary before it is passed to a backend.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"
_ALLOWED_UNITS = {"SI"}
_ALLOWED_STATUSES = {
    "accepted",
    "completed",
    "screening_only",
    "fail_screening",
    "rejected",
    "error",
}
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


def _finite_tree(value: Any, path: str = "value") -> None:
    """Reject non-finite numbers and unsupported objects recursively."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        _finite(value, path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _finite_tree(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            _finite_tree(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contains unsupported type {type(value).__name__}")


@dataclass(frozen=True)
class GeometrySpec:
    """Minimal geometry descriptor; dimensions are metres."""

    geometry_type: str
    parameters: dict[str, Any]
    coordinate_system: str = "right_handed_cartesian"

    def __post_init__(self) -> None:
        _non_empty(self.geometry_type, "geometry_type")
        _non_empty(self.coordinate_system, "coordinate_system")
        if not isinstance(self.parameters, dict):
            raise TypeError("geometry parameters must be an object")
        _finite_tree(self.parameters, "geometry.parameters")


@dataclass(frozen=True)
class LoadCase:
    """A named load case. Force is in newtons and moment in newton-metres."""

    name: str
    force_n: tuple[float, float, float] = (0.0, 0.0, 0.0)
    moment_nm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    description: str = ""

    def __post_init__(self) -> None:
        _non_empty(self.name, "load case name")
        for field_name, vector in (("force_n", self.force_n), ("moment_nm", self.moment_nm)):
            if len(vector) != 3:
                raise ValueError(f"{field_name} must contain exactly three components")
            for index, component in enumerate(vector):
                _finite(component, f"{field_name}[{index}]")


@dataclass(frozen=True)
class ArtifactReference:
    """Reference to a generated or source artifact, not the artifact itself."""

    artifact_id: str
    media_type: str
    uri: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("artifact_id", "media_type", "uri"):
            _non_empty(getattr(self, name), name)
        if not _ID_PATTERN.fullmatch(self.artifact_id):
            raise ValueError("artifact_id contains unsupported characters")
        if self.sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")


@dataclass(frozen=True)
class EngineeringRequest:
    """Canonical request exchanged between agents and engineering services."""

    request_id: str
    title: str
    objective: str
    geometry: GeometrySpec | None = None
    material: dict[str, Any] = field(default_factory=dict)
    load_cases: tuple[LoadCase, ...] = ()
    operating_conditions: dict[str, Any] = field(default_factory=dict)
    requirements: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    units_system: str = "SI"
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "title", "objective", "contract_version"):
            _non_empty(getattr(self, name), name)
        if not _ID_PATTERN.fullmatch(self.request_id):
            raise ValueError("request_id contains unsupported characters")
        if self.units_system not in _ALLOWED_UNITS:
            raise ValueError("Only SI units are accepted by contract version 1.0")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"Unsupported contract_version: {self.contract_version}")
        for name, value in (
            ("material", self.material),
            ("operating_conditions", self.operating_conditions),
        ):
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be an object")
            _finite_tree(value, name)
        for name, values in (("requirements", self.requirements), ("assumptions", self.assumptions)):
            if not all(isinstance(item, str) and item.strip() for item in values):
                raise ValueError(f"{name} must contain non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineeringRequest":
        if not isinstance(data, dict):
            raise TypeError("Engineering request must be a JSON object")
        payload = dict(data)
        geometry = payload.get("geometry")
        if geometry is not None and not isinstance(geometry, GeometrySpec):
            payload["geometry"] = GeometrySpec(**geometry)
        payload["load_cases"] = tuple(
            item if isinstance(item, LoadCase) else LoadCase(**item)
            for item in payload.get("load_cases", ())
        )
        return cls(**payload)

    @classmethod
    def from_json(cls, source: str) -> "EngineeringRequest":
        try:
            data = json.loads(
                source,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    ValueError(f"Invalid JSON numeric constant: {token}")
                ),
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid engineering request JSON: {exc}") from exc
        return cls.from_dict(data)


@dataclass(frozen=True)
class SolverProvenance:
    """Identifies the calculation method and software that produced a result."""

    solver_name: str
    solver_version: str
    method: str
    input_digest_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("solver_name", "solver_version", "method"):
            _non_empty(getattr(self, name), name)
        if self.input_digest_sha256 is not None and not re.fullmatch(
            r"[0-9a-fA-F]{64}", self.input_digest_sha256
        ):
            raise ValueError("input_digest_sha256 must be a 64-character SHA-256 digest")


@dataclass(frozen=True)
class EngineeringResponse:
    """Canonical result envelope returned by a CAD or physics service."""

    request_id: str
    status: str
    provenance: SolverProvenance
    values: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    artifacts: tuple[ArtifactReference, ...] = ()
    uncertainty: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _non_empty(self.request_id, "request_id")
        if not _ID_PATTERN.fullmatch(self.request_id):
            raise ValueError("request_id contains unsupported characters")
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unsupported result status: {self.status}")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"Unsupported contract_version: {self.contract_version}")
        for name, value in (("values", self.values), ("units", self.units), ("uncertainty", self.uncertainty)):
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be an object")
            _finite_tree(value, name)
        if not all(isinstance(key, str) and isinstance(unit, str) for key, unit in self.units.items()):
            raise TypeError("units must map string value names to unit strings")
        for name, items in (
            ("assumptions", self.assumptions),
            ("warnings", self.warnings),
            ("limitations", self.limitations),
        ):
            if not all(isinstance(item, str) and item.strip() for item in items):
                raise ValueError(f"{name} must contain non-empty strings")
        if not isinstance(self.provenance, SolverProvenance):
            raise TypeError("provenance must be a SolverProvenance")
        if not all(isinstance(item, ArtifactReference) for item in self.artifacts):
            raise TypeError("artifacts must contain ArtifactReference values")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineeringResponse":
        if not isinstance(data, dict):
            raise TypeError("Engineering response must be a JSON object")
        payload = dict(data)
        provenance = payload.get("provenance")
        if provenance is not None and not isinstance(provenance, SolverProvenance):
            payload["provenance"] = SolverProvenance(**provenance)
        payload["artifacts"] = tuple(
            item if isinstance(item, ArtifactReference) else ArtifactReference(**item)
            for item in payload.get("artifacts", ())
        )
        for name in ("assumptions", "warnings", "limitations"):
            if name in payload:
                payload[name] = tuple(payload[name])
        return cls(**payload)

    @classmethod
    def from_json(cls, source: str) -> "EngineeringResponse":
        try:
            data = json.loads(
                source,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    ValueError(f"Invalid JSON numeric constant: {token}")
                ),
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid engineering response JSON: {exc}") from exc
        return cls.from_dict(data)
