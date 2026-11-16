"""Typed, frame-aware solver boundary for shared YJ64 physical-kernel inputs.

This contract transports existing Quantity, CoordinateFrameRegistry, AppliedLoad
and BoundaryCondition objects without flattening them into ambiguous dictionaries.
It is solver-neutral; mesh mapping and discipline equations remain adapter-owned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Protocol

from .physics.kernel.conditions import AppliedLoad, BoundaryCondition
from .physics.kernel.coordinate_frames import CoordinateFrameRegistry
from .physics.kernel.quantities import Quantity


def _non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _json_safe(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, ensure_ascii=False, allow_nan=False)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain finite JSON-compatible values: {exc}") from exc
    return decoded


@dataclass(frozen=True, slots=True)
class TypedSolverRequest:
    """Immutable solver input retaining physical dimensions and frame identity."""

    request_id: str
    operation: str
    frame_registry: CoordinateFrameRegistry = field(compare=False, repr=False)
    loads: tuple[AppliedLoad, ...] = ()
    boundary_conditions: tuple[BoundaryCondition, ...] = ()
    quantities: Mapping[str, Quantity] = field(default_factory=dict)
    component_dependencies: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _non_empty(self.request_id, "request_id")
        _non_empty(self.operation, "operation")
        if not isinstance(self.frame_registry, CoordinateFrameRegistry):
            raise TypeError("frame_registry must be a CoordinateFrameRegistry")
        if not isinstance(self.loads, tuple) or any(not isinstance(x, AppliedLoad) for x in self.loads):
            raise TypeError("loads must be a tuple of AppliedLoad values")
        if not isinstance(self.boundary_conditions, tuple) or any(
            not isinstance(x, BoundaryCondition) for x in self.boundary_conditions
        ):
            raise TypeError("boundary_conditions must be a tuple of BoundaryCondition values")
        load_ids = [item.load_id for item in self.loads]
        condition_ids = [item.condition_id for item in self.boundary_conditions]
        if len(load_ids) != len(set(load_ids)):
            raise ValueError("load IDs must be unique within a solver request")
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("boundary-condition IDs must be unique within a solver request")
        known_frames = set(self.frame_registry.ids())
        for load in self.loads:
            if load.frame_id not in known_frames:
                raise ValueError(f"load '{load.load_id}' references unknown frame '{load.frame_id}'")
        for condition in self.boundary_conditions:
            if condition.frame_id not in known_frames:
                raise ValueError(
                    f"boundary condition '{condition.condition_id}' references "
                    f"unknown frame '{condition.frame_id}'"
                )
        if not isinstance(self.quantities, Mapping):
            raise TypeError("quantities must be a mapping of names to Quantity values")
        normalized_quantities: dict[str, Quantity] = {}
        for name, quantity in self.quantities.items():
            _non_empty(name, "quantity name")
            if not isinstance(quantity, Quantity):
                raise TypeError(f"quantity '{name}' must be a Quantity")
            normalized_quantities[name] = quantity
        object.__setattr__(self, "quantities", normalized_quantities)
        normalized_dependencies: list[dict[str, Any]] = []
        seen_dependencies: set[str] = set()
        for dependency in self.component_dependencies:
            if not isinstance(dependency, Mapping):
                raise TypeError("component dependencies must be mappings")
            component_id = dependency.get("component_id")
            revision = dependency.get("revision")
            _non_empty(component_id, "dependency component_id")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
                raise ValueError("dependency revision must be a positive integer")
            if component_id in seen_dependencies:
                raise ValueError("component dependency IDs must be unique")
            seen_dependencies.add(component_id)
            normalized_dependencies.append({"component_id": component_id, "revision": revision})
        object.__setattr__(self, "component_dependencies", tuple(normalized_dependencies))

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON representation for hashing and provenance."""
        frames = []
        for frame_id in sorted(self.frame_registry.ids()):
            frame = self.frame_registry.get(frame_id)
            frames.append({
                "frame_id": frame.frame_id,
                "parent_id": frame.parent_id,
                "rotation_to_parent": frame.rotation_to_parent,
                "translation_to_parent_m": frame.translation_to_parent_m,
            })
        loads = []
        for load in self.loads:
            point = load.application_point
            loads.append({
                "load_id": load.load_id,
                "target_id": load.target_id,
                "kind": load.kind,
                "components": [component.to_dict() for component in load.components],
                "frame_id": load.frame_id,
                "distribution": load.distribution,
                "application_point": None if point is None else {
                    "coordinates_m": point.coordinates_m,
                    "frame_id": point.frame_id,
                },
                "description": load.description,
            })
        conditions = [{
            "condition_id": condition.condition_id,
            "target_id": condition.target_id,
            "kind": condition.kind,
            "components": [component.to_dict() for component in condition.components],
            "frame_id": condition.frame_id,
            "description": condition.description,
        } for condition in self.boundary_conditions]
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "frames": frames,
            "loads": loads,
            "boundary_conditions": conditions,
            "quantities": {
                name: self.quantities[name].to_dict() for name in sorted(self.quantities)
            },
            "component_dependencies": list(self.component_dependencies),
        }


@dataclass(frozen=True, slots=True)
class TypedSolverResult:
    """Solver-owned result payload before the dispatcher adds provenance."""

    status: str
    method: str
    values: Mapping[str, Any]
    units: Mapping[str, str]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in ("completed", "screening_only", "error"):
            raise ValueError("unsupported typed solver result status")
        _non_empty(self.method, "method")
        object.__setattr__(self, "values", _json_safe(self.values, "values"))
        object.__setattr__(self, "units", _json_safe(self.units, "units"))
        for name in ("assumptions", "warnings", "limitations"):
            items = getattr(self, name)
            if not isinstance(items, tuple) or not all(isinstance(x, str) for x in items):
                raise TypeError(f"{name} must be a tuple of strings")


class TypedPhysicsSolver(Protocol):
    """Minimal protocol for a solver consuming typed shared-kernel inputs."""

    name: str
    version: str

    def supports(self, operation: str) -> bool: ...
    def solve(self, request: TypedSolverRequest) -> TypedSolverResult: ...


@dataclass(frozen=True, slots=True)
class TypedSolverResponse:
    request_id: str
    operation: str
    status: str
    solver_name: str
    solver_version: str
    method: str
    input_digest_sha256: str
    values: Mapping[str, Any]
    units: Mapping[str, str]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "status": self.status,
            "solver_name": self.solver_name,
            "solver_version": self.solver_version,
            "method": self.method,
            "input_digest_sha256": self.input_digest_sha256,
            "values": dict(self.values),
            "units": dict(self.units),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


class TypedSolverDispatcher:
    """Dispatch typed requests without implicit unit or coordinate conversions."""

    def __init__(self) -> None:
        self._solvers: list[TypedPhysicsSolver] = []

    def register(self, solver: TypedPhysicsSolver) -> None:
        if not callable(getattr(solver, "supports", None)) or not callable(
            getattr(solver, "solve", None)
        ):
            raise TypeError("typed solver must implement supports() and solve()")
        if not getattr(solver, "name", None) or not getattr(solver, "version", None):
            raise ValueError("typed solver must declare name and version")
        if any(item.name == solver.name and item.version == solver.version for item in self._solvers):
            raise ValueError("typed solver name/version is already registered")
        self._solvers.append(solver)

    def dispatch(self, request: TypedSolverRequest) -> TypedSolverResponse:
        if not isinstance(request, TypedSolverRequest):
            raise TypeError("request must be a TypedSolverRequest")
        solver = next((item for item in self._solvers if item.supports(request.operation)), None)
        if solver is None:
            raise LookupError(f"No typed solver supports operation: {request.operation}")
        canonical = json.dumps(
            request.to_canonical_dict(), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        result = solver.solve(request)
        if not isinstance(result, TypedSolverResult):
            raise TypeError("typed solver must return TypedSolverResult")
        return TypedSolverResponse(
            request_id=request.request_id,
            operation=request.operation,
            status=result.status,
            solver_name=solver.name,
            solver_version=solver.version,
            method=result.method,
            input_digest_sha256=digest,
            values=result.values,
            units=result.units,
            assumptions=result.assumptions,
            warnings=result.warnings,
            limitations=result.limitations,
        )
