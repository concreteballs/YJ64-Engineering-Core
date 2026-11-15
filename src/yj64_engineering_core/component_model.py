"""Revisioned, solver-neutral engineering component model.

This is the shared data layer for CAD, physics, materials and manufacturing.
It deliberately stores inputs and evidence; it does not claim that a component
is structurally safe or manufacturable merely because it is representable.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import GeometrySpec

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_STATES = {
    "concept",
    "screened",
    "simulated",
    "reviewed",
    "prototype_manufactured",
    "bench_tested",
    "field_tested",
    "qualified",
    "superseded",
}


def _identifier(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{field_name} must be a non-empty engineering identifier")


def _finite_tree(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _finite_tree(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            _finite_tree(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} contains unsupported value type: {type(value).__name__}")


@dataclass(frozen=True)
class ComponentMassProperties:
    """Mass properties in SI units; inertia is about the stated CG."""

    mass_kg: float
    center_of_gravity_m: tuple[float, float, float] | None = None
    inertia_tensor_kg_m2: tuple[tuple[float, float, float], ...] | None = None

    def __post_init__(self) -> None:
        _finite_tree(self.mass_kg, "mass_kg")
        if isinstance(self.mass_kg, bool) or self.mass_kg < 0:
            raise ValueError("mass_kg must be non-negative")
        if self.center_of_gravity_m is not None:
            if len(self.center_of_gravity_m) != 3:
                raise ValueError("center_of_gravity_m must have three coordinates")
            _finite_tree(self.center_of_gravity_m, "center_of_gravity_m")
        if self.inertia_tensor_kg_m2 is not None:
            tensor = self.inertia_tensor_kg_m2
            if len(tensor) != 3 or any(len(row) != 3 for row in tensor):
                raise ValueError("inertia_tensor_kg_m2 must be a 3x3 matrix")
            _finite_tree(tensor, "inertia_tensor_kg_m2")
            for i in range(3):
                for j in range(3):
                    if not math.isclose(tensor[i][j], tensor[j][i], rel_tol=1e-9, abs_tol=1e-12):
                        raise ValueError("inertia tensor must be symmetric")
            if any(tensor[i][i] < 0 for i in range(3)):
                raise ValueError("inertia tensor diagonal values must be non-negative")


@dataclass(frozen=True)
class ComponentDependency:
    """A pinned dependency on an exact revision of another component."""

    component_id: str
    revision: int
    purpose: str

    def __post_init__(self) -> None:
        _identifier(self.component_id, "dependency component_id")
        if isinstance(self.revision, bool) or self.revision < 1:
            raise ValueError("dependency revision must be a positive integer")
        if not self.purpose.strip():
            raise ValueError("dependency purpose cannot be empty")


@dataclass(frozen=True)
class ComponentInterface:
    """A named physical or functional connection to another component."""

    name: str
    interface_type: str
    target_component_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.interface_type.strip():
            raise ValueError("interface name and interface_type cannot be empty")
        if self.target_component_id is not None:
            _identifier(self.target_component_id, "target_component_id")
        _finite_tree(self.parameters, "interface.parameters")


@dataclass(frozen=True)
class ManufacturingConstraint:
    """Process constraints; values are process-specific and remain explicit."""

    process: str
    parameters: dict[str, Any] = field(default_factory=dict)
    source: str | None = None

    def __post_init__(self) -> None:
        if not self.process.strip():
            raise ValueError("manufacturing process cannot be empty")
        _finite_tree(self.parameters, "manufacturing.parameters")
        if self.source is not None and not self.source.strip():
            raise ValueError("manufacturing source cannot be blank")


@dataclass(frozen=True)
class EvidenceRecord:
    """Traceable evidence supporting a component lifecycle state."""

    evidence_id: str
    evidence_type: str
    description: str
    source_uri: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.evidence_id, "evidence_id")
        if not self.evidence_type.strip() or not self.description.strip():
            raise ValueError("evidence_type and description cannot be empty")
        if self.sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256):
            raise ValueError("evidence sha256 must be a 64-character hexadecimal digest")


@dataclass(frozen=True)
class EngineeringComponent:
    """Canonical, revisioned description of a part, assembly or system node."""

    component_id: str
    revision: int
    name: str
    component_type: str
    geometry: GeometrySpec | None = None
    material: dict[str, Any] = field(default_factory=dict)
    mass_properties: ComponentMassProperties | None = None
    parent_component_ids: tuple[str, ...] = ()
    dependencies: tuple[ComponentDependency, ...] = ()
    interfaces: tuple[ComponentInterface, ...] = ()
    manufacturing_constraints: tuple[ManufacturingConstraint, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    lifecycle_state: str = "concept"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier(self.component_id, "component_id")
        if isinstance(self.revision, bool) or self.revision < 1:
            raise ValueError("component revision must be a positive integer")
        if not self.name.strip() or not self.component_type.strip():
            raise ValueError("component name and component_type cannot be empty")
        if self.lifecycle_state not in _STATES:
            raise ValueError(f"Unsupported lifecycle_state: {self.lifecycle_state}")
        if self.component_id in self.parent_component_ids:
            raise ValueError("component cannot be its own parent")
        if len(set(self.parent_component_ids)) != len(self.parent_component_ids):
            raise ValueError("parent_component_ids must be unique")
        for item in self.parent_component_ids:
            _identifier(item, "parent_component_id")
        dependency_ids = [item.component_id for item in self.dependencies]
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("dependencies must contain one pinned revision per component")
        if self.component_id in dependency_ids:
            raise ValueError("component cannot depend on itself")
        _finite_tree(self.material, "material")
        _finite_tree(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation with stable field names."""
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True)

    def fingerprint(self) -> str:
        """SHA-256 of this exact component revision and its declared inputs."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def stale_component_dependencies(
    components: tuple[EngineeringComponent, ...] | list[EngineeringComponent],
    current_revisions: dict[str, int],
) -> dict[str, tuple[str, ...]]:
    """Return components whose pinned dependency revisions are no longer current.

    Missing dependencies are stale too. This is a direct dependency check;
    callers can apply it repeatedly to propagate invalidation through a graph.
    """
    _finite_tree(current_revisions, "current_revisions")
    stale: dict[str, tuple[str, ...]] = {}
    for component in components:
        outdated = tuple(
            dependency.component_id
            for dependency in component.dependencies
            if current_revisions.get(dependency.component_id) != dependency.revision
        )
        if outdated:
            stale[component.component_id] = outdated
    return stale
