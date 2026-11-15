"""Panel-wise hydrostatic pressure loads for wetted vessel surfaces.

This module generates distributed pressure loads and their force/moment
resultants. It does not calculate shell, stiffener or hull-girder stresses.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vector(value: Any, name: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three numeric values")
    return tuple(_number(item, f"{name}[{index}]") for index, item in enumerate(value))


class HydrostaticPanelLoadSolver:
    """Convert surface panels into signed differential-pressure loads."""

    name = "YJ64 hydrostatic panel pressure-load generator"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "hydrostatics.panel_pressure_loads"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        geometry = p.get("geometry") or {}
        conditions = p.get("operating_conditions") or {}
        panels = geometry.get("panels")
        if not isinstance(panels, list) or not panels:
            raise ValueError("geometry.panels must be a non-empty list")

        waterline = _number(conditions.get("waterline_z_m"), "waterline_z_m")
        density = _number(conditions.get("water_density_kg_m3", 1025.0), "water_density_kg_m3")
        gravity = _number(conditions.get("gravity_m_s2", 9.80665), "gravity_m_s2")
        internal_pressure = _number(
            conditions.get("internal_gauge_pressure_pa", 0.0),
            "internal_gauge_pressure_pa",
        )
        if density <= 0.0 or gravity <= 0.0:
            raise ValueError("water density and gravity must be positive")

        seen_ids: set[str] = set()
        panel_results: list[dict[str, Any]] = []
        total_force = [0.0, 0.0, 0.0]
        total_moment = [0.0, 0.0, 0.0]
        total_area = 0.0
        max_external_pressure = 0.0

        for index, panel in enumerate(panels):
            if not isinstance(panel, dict):
                raise TypeError(f"panels[{index}] must be an object")
            panel_id = panel.get("panel_id")
            if not isinstance(panel_id, str) or not panel_id.strip():
                raise ValueError(f"panels[{index}].panel_id must be a non-empty string")
            if panel_id in seen_ids:
                raise ValueError(f"duplicate panel_id: {panel_id}")
            seen_ids.add(panel_id)

            area = _number(panel.get("area_m2"), f"panels[{index}].area_m2")
            if area <= 0.0:
                raise ValueError(f"panels[{index}].area_m2 must be positive")
            centroid = _vector(panel.get("centroid_m"), f"panels[{index}].centroid_m")
            normal = _vector(panel.get("outward_normal"), f"panels[{index}].outward_normal")
            normal_length = math.sqrt(sum(component * component for component in normal))
            if not math.isclose(normal_length, 1.0, rel_tol=1e-6, abs_tol=1e-6):
                raise ValueError(f"panels[{index}].outward_normal must be a unit vector")

            depth = max(0.0, waterline - centroid[2])
            external_pressure = density * gravity * depth
            differential_pressure = external_pressure - internal_pressure
            force = tuple(-differential_pressure * area * component for component in normal)
            moment = (
                centroid[1] * force[2] - centroid[2] * force[1],
                centroid[2] * force[0] - centroid[0] * force[2],
                centroid[0] * force[1] - centroid[1] * force[0],
            )
            for axis in range(3):
                total_force[axis] += force[axis]
                total_moment[axis] += moment[axis]
            total_area += area
            max_external_pressure = max(max_external_pressure, external_pressure)
            panel_results.append({
                "panel_id": panel_id,
                "area_m2": area,
                "centroid_m": list(centroid),
                "depth_below_waterline_m": depth,
                "external_hydrostatic_pressure_pa": external_pressure,
                "internal_gauge_pressure_pa": internal_pressure,
                "differential_pressure_pa": differential_pressure,
                "force_xyz_n": list(force),
                "moment_about_origin_xyz_nm": list(moment),
                "loading_direction": (
                    "inward" if differential_pressure > 0.0
                    else "outward" if differential_pressure < 0.0
                    else "zero"
                ),
            })

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="load_generation_only",
            values={
                "panel_count": len(panel_results),
                "total_panel_area_m2": total_area,
                "maximum_external_hydrostatic_pressure_pa": max_external_pressure,
                "total_force_xyz_n": total_force,
                "total_moment_about_origin_xyz_nm": total_moment,
                "panels": panel_results,
            },
            units={
                "panel_count": "count",
                "total_panel_area_m2": "m^2",
                "maximum_external_hydrostatic_pressure_pa": "Pa",
                "total_force_xyz_n": "N",
                "total_moment_about_origin_xyz_nm": "N*m",
                "panels": "structured",
            },
            method="centroid_panel_hydrostatic_pressure_with_signed_internal_external_differential_and_force_moment_resultants",
            assumptions=[
                "Each panel is represented by its area, centroid and outward unit normal.",
                "Pressure is evaluated at each panel centroid; panel pressure is treated as uniform over that panel.",
                "The waterline is horizontal and water density and gravity are uniform.",
                "Internal gauge pressure is uniform over all supplied panels.",
                "Panel force acts opposite the outward normal for positive external-minus-internal differential pressure.",
                "Moments are calculated about the global coordinate origin using each panel centroid.",
            ],
            warnings=[
                "This is a pressure-load generator, not a structural stress or scantling solver.",
                "Panel size and mesh density must resolve pressure gradients and geometric curvature adequately.",
                "Above-water panels have zero external hydrostatic pressure; supplied internal gauge pressure still acts on them.",
            ],
            limitations=[
                "No panel geometry validation, mesh connectivity, pressure interpolation or curved-panel integration.",
                "No trim, heel, acceleration, wave pressure, slamming, impact, grounding or transient fluid effects.",
                "No shell, laminate, stiffener, frame, bulkhead, joint or global hull-girder stress analysis.",
                "No hydrostatic equilibrium or buoyancy-volume integration; use the separate hydrostatics solver for displacement estimates.",
                "No pressure-field coupling to FEM boundary conditions or automatic load transfer yet.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
