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
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
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
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
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
    if any(
        not isinstance(component_id, str)
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        for component_id, revision in current_revisions.items()
    ):
        raise ValueError("current_revisions must map component IDs to positive integer revisions")
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


@dataclass(frozen=True)
class ComponentCalculationRecord:
    """Immutable link between a calculation result and exact component revisions."""

    calculation_id: str
    operation: str
    input_digest_sha256: str
    component_dependencies: tuple[ComponentDependency, ...]
    result_digest_sha256: str | None = None
    artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.calculation_id, "calculation_id")
        if not self.operation.strip():
            raise ValueError("calculation operation cannot be empty")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.input_digest_sha256):
            raise ValueError("input_digest_sha256 must be a 64-character SHA-256 digest")
        if self.result_digest_sha256 is not None and not re.fullmatch(
            r"[0-9a-fA-F]{64}", self.result_digest_sha256
        ):
            raise ValueError("result_digest_sha256 must be a 64-character SHA-256 digest")
        dependency_ids = [item.component_id for item in self.component_dependencies]
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("calculation dependencies must be unique")
        for artifact_id in self.artifact_ids:
            _identifier(artifact_id, "artifact_id")

    def fingerprint(self) -> str:
        payload = json.dumps(
            asdict(self), ensure_ascii=False, allow_nan=False, sort_keys=True
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stale_calculations(
    calculations: tuple[ComponentCalculationRecord, ...] | list[ComponentCalculationRecord],
    current_revisions: dict[str, int],
) -> dict[str, tuple[str, ...]]:
    """Identify calculations pinned to missing or superseded component revisions."""
    if any(
        not isinstance(component_id, str)
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        for component_id, revision in current_revisions.items()
    ):
        raise ValueError("current_revisions must map component IDs to positive integer revisions")
    stale: dict[str, tuple[str, ...]] = {}
    for calculation in calculations:
        outdated = tuple(
            dependency.component_id
            for dependency in calculation.component_dependencies
            if current_revisions.get(dependency.component_id) != dependency.revision
        )
        if outdated:
            stale[calculation.calculation_id] = outdated
    return stale


class EngineeringProjectGraph:
    """In-memory component/dependency registry with transitive stale propagation.

    Persistence, collaboration/locking and automatic solver reruns are intentionally
    outside this first graph implementation.
    """

    def __init__(self) -> None:
        self._components: dict[str, EngineeringComponent] = {}
        self._calculations: dict[str, ComponentCalculationRecord] = {}

    @property
    def components(self) -> dict[str, EngineeringComponent]:
        return dict(self._components)

    @property
    def calculations(self) -> dict[str, ComponentCalculationRecord]:
        return dict(self._calculations)

    def add_component(self, component: EngineeringComponent) -> None:
        if not isinstance(component, EngineeringComponent):
            raise TypeError("component must be an EngineeringComponent")
        if component.component_id in self._components:
            raise ValueError(f"Component already exists: {component.component_id}")
        self._validate_component_links(component, self._components)
        candidate = dict(self._components)
        candidate[component.component_id] = component
        self._assert_acyclic(candidate)
        self._components = candidate

    def replace_component(self, component: EngineeringComponent) -> None:
        if not isinstance(component, EngineeringComponent):
            raise TypeError("component must be an EngineeringComponent")
        previous = self._components.get(component.component_id)
        if previous is None:
            raise KeyError(f"Unknown component: {component.component_id}")
        if component.revision <= previous.revision:
            raise ValueError("replacement component revision must increase")
        candidate = dict(self._components)
        candidate[component.component_id] = component
        self._validate_component_links(component, candidate)
        self._assert_acyclic(candidate)
        self._components = candidate

    def add_calculation(self, calculation: ComponentCalculationRecord) -> None:
        if not isinstance(calculation, ComponentCalculationRecord):
            raise TypeError("calculation must be a ComponentCalculationRecord")
        if calculation.calculation_id in self._calculations:
            raise ValueError(f"Calculation already exists: {calculation.calculation_id}")
        for dependency in calculation.component_dependencies:
            current = self._components.get(dependency.component_id)
            if current is None or current.revision != dependency.revision:
                raise ValueError(
                    f"Calculation dependency is missing or stale: {dependency.component_id}"
                )
        stale_components = self.stale_component_ids()
        affected = sorted(
            dependency.component_id
            for dependency in calculation.component_dependencies
            if dependency.component_id in stale_components
        )
        if affected:
            raise ValueError(
                "Cannot register a calculation against stale components: "
                + ", ".join(affected)
            )
        self._calculations[calculation.calculation_id] = calculation

    def stale_component_ids(self) -> set[str]:
        """Return direct and transitively affected component IDs."""
        stale: set[str] = set()
        changed = True
        while changed:
            changed = False
            for component in self._components.values():
                if component.component_id in stale:
                    continue
                invalid_dependency = any(
                    dependency.component_id in stale
                    or (
                        dependency.component_id not in self._components
                        or self._components[dependency.component_id].revision
                        != dependency.revision
                    )
                    for dependency in component.dependencies
                )
                if invalid_dependency:
                    stale.add(component.component_id)
                    changed = True
        return stale

    def stale_calculation_ids(self) -> set[str]:
        """Return calculations directly or transitively affected by stale inputs."""
        stale_components = self.stale_component_ids()
        stale: set[str] = set()
        for calculation in self._calculations.values():
            if any(
                dependency.component_id in stale_components
                or dependency.component_id not in self._components
                or self._components[dependency.component_id].revision != dependency.revision
                for dependency in calculation.component_dependencies
            ):
                stale.add(calculation.calculation_id)
        return stale

    @staticmethod
    def _validate_component_links(
        component: EngineeringComponent,
        available: dict[str, EngineeringComponent],
    ) -> None:
        for parent_id in component.parent_component_ids:
            if parent_id not in available:
                raise ValueError(f"Unknown parent component: {parent_id}")
        for dependency in component.dependencies:
            target = available.get(dependency.component_id)
            if target is None:
                raise ValueError(f"Unknown dependency component: {dependency.component_id}")
            if target.revision != dependency.revision:
                raise ValueError(
                    f"Dependency revision mismatch for {dependency.component_id}: "
                    f"requested {dependency.revision}, current {target.revision}"
                )

    @staticmethod
    def _assert_acyclic(components: dict[str, EngineeringComponent]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(component_id: str) -> None:
            if component_id in visiting:
                raise ValueError(f"Component dependency cycle detected at {component_id}")
            if component_id in visited:
                return
            visiting.add(component_id)
            component = components[component_id]
            for dependency in component.dependencies:
                if dependency.component_id in components:
                    visit(dependency.component_id)
            visiting.remove(component_id)
            visited.add(component_id)

        for component_id in components:
            visit(component_id)
