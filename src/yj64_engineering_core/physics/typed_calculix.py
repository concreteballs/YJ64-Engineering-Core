"""Typed shared-kernel adapter for a constrained CalculiX axial-member FEM case.

This adapter supports one straight, prismatic, linearly elastic axial member.
It maps explicit YJ64 target IDs to the two nodes of a generated T3D2 mesh;
it is not a general geometry-to-mesh or load-mapping engine.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..models import AnalysisRequest
from ..typed_solver import TypedSolverRequest, TypedSolverResult
from .calculix import CalculiXTrussSolver
from .kernel.conditions import AppliedLoad, BoundaryCondition
from .kernel.quantities import DIMENSIONLESS, LENGTH, PRESSURE, Quantity

AREA = (0, 2, 0, 0, 0, 0, 0)


def _si_quantity(
    request: TypedSolverRequest,
    name: str,
    dimension: tuple[int, ...],
    *,
    positive: bool = False,
) -> float:
    try:
        quantity = request.quantities[name]
    except KeyError as exc:
        raise ValueError(f"missing required quantity: {name}") from exc
    if not isinstance(quantity, Quantity) or quantity.dimension != dimension:
        raise ValueError(f"{name} has an incompatible physical dimension")
    value = quantity.si_value
    if not math.isfinite(value) or (positive and value <= 0):
        qualifier = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}")
    return value


def _near_zero(value: float, scale: float = 1.0) -> bool:
    return abs(value) <= max(1e-10, abs(scale) * 1e-9)


class TypedCalculiXAxialTrussSolver:
    """Typed adapter for one member with a fixed root and axial tip force."""

    name = "CalculiX typed axial-truss FEM adapter"
    version = "1.0.0"
    operation = "structural.axial_truss_fem"

    def __init__(
        self,
        workspace: str | Path,
        executable: str = "ccx",
        timeout_seconds: float = 60.0,
        solver: Any | None = None,
    ) -> None:
        self._solver = solver or CalculiXTrussSolver(
            workspace, executable=executable, timeout_seconds=timeout_seconds
        )

    def supports(self, operation: str) -> bool:
        return operation == self.operation

    def solve(self, request: TypedSolverRequest) -> TypedSolverResult:
        if not self.supports(request.operation):
            raise ValueError(f"unsupported operation: {request.operation}")

        length_m = _si_quantity(request, "member_length", LENGTH, positive=True)
        area_m2 = _si_quantity(request, "cross_section_area", AREA, positive=True)
        youngs_modulus_pa = _si_quantity(
            request, "youngs_modulus", PRESSURE, positive=True
        )
        poisson_ratio = _si_quantity(request, "poisson_ratio", DIMENSIONLESS)
        if not -1.0 < poisson_ratio < 0.5:
            raise ValueError("poisson_ratio must be between -1 and 0.5")

        if len(request.loads) != 1:
            raise ValueError("this operation requires exactly one applied load")
        load: AppliedLoad = request.loads[0]
        if load.kind != "force" or load.target_id != "member:tip":
            raise ValueError("the single load must be a force targeting 'member:tip'")
        if load.distribution != "point":
            raise ValueError("only a point load at the member tip is supported")

        if len(request.boundary_conditions) != 1:
            raise ValueError("this operation requires exactly one boundary condition")
        boundary: BoundaryCondition = request.boundary_conditions[0]
        if boundary.kind != "fixed" or boundary.target_id != "member:root":
            raise ValueError("the boundary condition must fix 'member:root'")

        world_frame = "world"
        if world_frame not in request.frame_registry.ids():
            raise ValueError("the coordinate-frame registry must contain the 'world' frame")

        force_local = tuple(component.si_value for component in load.components)
        force_transform = request.frame_registry.transform(load.frame_id, world_frame)
        fx, fy, fz = force_transform.apply_vector(force_local)
        force_scale = max(abs(fx), abs(fy), abs(fz), 1.0)
        if not _near_zero(fx, force_scale) or not _near_zero(fy, force_scale):
            raise ValueError("the applied force must be aligned with the member world Z axis")
        if _near_zero(fz, force_scale):
            raise ValueError("the applied axial force must be non-zero")

        if load.application_point is None:
            raise ValueError("the tip force must include an explicit application point")
        point_transform = request.frame_registry.transform(
            load.application_point.frame_id, world_frame
        )
        point_world = point_transform.apply_point(load.application_point.coordinates_m)
        if (
            not _near_zero(point_world[0], length_m)
            or not _near_zero(point_world[1], length_m)
            or not math.isclose(
                point_world[2], length_m, rel_tol=1e-9, abs_tol=1e-10
            )
        ):
            raise ValueError(
                "the load application point must coincide with the member tip (0, 0, L)"
            )

        if boundary.frame_id != world_frame:
            raise ValueError("the fixed root boundary condition must be expressed in 'world'")

        analysis = AnalysisRequest(
            analysis_type="axial_truss_fem",
            parameters={
                "request_id": request.request_id,
                "force_n": fz,
                "area_m2": area_m2,
                "length_m": length_m,
                "material": {
                    "name": "YJ64 typed material",
                    "youngs_modulus_pa": youngs_modulus_pa,
                    "poisson_ratio": poisson_ratio,
                },
            },
        )
        result = self._solver.solve(analysis)
        values = dict(result.values)
        units = dict(result.units)
        values.update(
            {
                "applied_force_world_n": [fx, fy, fz],
                "member_length_m": length_m,
                "cross_section_area_m2": area_m2,
                "youngs_modulus_pa": youngs_modulus_pa,
                "poisson_ratio": poisson_ratio,
                "external_solver_version": result.solver_version,
            }
        )
        units.update(
            {
                "applied_force_world_n": "N",
                "member_length_m": "m",
                "cross_section_area_m2": "m^2",
                "youngs_modulus_pa": "Pa",
                "poisson_ratio": "dimensionless",
                "external_solver_version": "text",
            }
        )
        return TypedSolverResult(
            status="completed",
            method=result.method,
            values=values,
            units=units,
            assumptions=tuple(result.assumptions)
            + (
                "YJ64 target 'member:root' maps to the fixed first node.",
                "YJ64 target 'member:tip' maps to the second node at world coordinate (0, 0, L).",
                "Load vectors are explicitly transformed into the world frame before mapping.",
            ),
            warnings=tuple(result.warnings),
            limitations=tuple(result.limitations)
            + (
                "Only one axial T3D2 member, one point force and one fixed-root condition are supported.",
                "No general CAD geometry, mesh entity, distributed-load or multi-member mapping is implemented.",
            ),
        )
