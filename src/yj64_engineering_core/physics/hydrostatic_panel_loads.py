"""Hydrostatic pressure loads on hull surface panels.

Panels may use the legacy centroid approximation or explicit convex polygon
vertices for exact integration of the linear hydrostatic pressure field.
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


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _polygon_integrals(vertices, normal, waterline, density, gravity, internal):
    """Integrate pressure and position*pressure over a convex planar polygon."""
    if len(vertices) < 3:
        raise ValueError("vertices_m must contain at least three points")
    heights = [waterline - point[2] for point in vertices]
    if any(h > 1e-9 for h in heights) and any(h < -1e-9 for h in heights):
        raise ValueError("polygon crosses the waterline; split it at the waterline")
    wet = all(h >= -1e-9 for h in heights)
    pressures = [density * gravity * max(0.0, h) - internal for h in heights]

    area_total = 0.0
    pressure_area = 0.0
    position_pressure = [0.0, 0.0, 0.0]
    origin = vertices[0]
    orientation = 0.0
    for i in range(1, len(vertices) - 1):
        tri = (origin, vertices[i], vertices[i + 1])
        cross = _cross(
            tuple(tri[1][j] - tri[0][j] for j in range(3)),
            tuple(tri[2][j] - tri[0][j] for j in range(3)),
        )
        signed = _dot(cross, normal)
        if abs(signed) <= 1e-12:
            raise ValueError("polygon contains a degenerate triangle")
        if orientation == 0.0:
            orientation = math.copysign(1.0, signed)
        elif signed * orientation <= 0.0:
            raise ValueError("vertices_m must describe a convex polygon ordered consistently")
        area = abs(signed) * 0.5
        p = (pressures[0], pressures[i], pressures[i + 1])
        sum_p = sum(p)
        integral_p = area * sum_p / 3.0
        area_total += area
        pressure_area += integral_p
        # Exact integral of r*p over a linear triangular pressure field.
        for axis in range(3):
            sum_r = tri[0][axis] + tri[1][axis] + tri[2][axis]
            diagonal = sum(tri[k][axis] * p[k] for k in range(3))
            position_pressure[axis] += area * (sum_r * sum_p + diagonal) / 12.0

    if not wet and any(h > 1e-9 for h in heights):
        raise ValueError("polygon crosses the waterline; split it at the waterline")
    return area_total, pressure_area, tuple(position_pressure), pressures


class HydrostaticPanelLoadSolver:
    """Convert surface panels into signed differential-pressure loads."""

    name = "YJ64 hydrostatic panel pressure-load generator"
    version = "0.2.0"

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
        internal_pressure = _number(conditions.get("internal_gauge_pressure_pa", 0.0), "internal_gauge_pressure_pa")
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
            normal_length = math.sqrt(_dot(normal, normal))
            if not math.isclose(normal_length, 1.0, rel_tol=1e-6, abs_tol=1e-6):
                raise ValueError(f"panels[{index}].outward_normal must be a unit vector")

            if "vertices_m" in panel:
                raw_vertices = panel["vertices_m"]
                if not isinstance(raw_vertices, (list, tuple)):
                    raise TypeError(f"panels[{index}].vertices_m must be a list")
                vertices = [_vector(v, f"panels[{index}].vertices_m[{j}]") for j, v in enumerate(raw_vertices)]
                # Reject non-planar vertices rather than silently projecting geometry.
                for vertex in vertices:
                    distance = _dot(tuple(vertex[j] - vertices[0][j] for j in range(3)), normal)
                    if abs(distance) > 1e-7:
                        raise ValueError("vertices_m must be planar and perpendicular to outward_normal")
                polygon_area, pressure_area, position_pressure, vertex_pressures = _polygon_integrals(
                    vertices, normal, waterline, density, gravity, internal_pressure
                )
                if not math.isclose(polygon_area, area, rel_tol=1e-5, abs_tol=1e-8):
                    raise ValueError("area_m2 does not match polygon vertices_m area")
                pressure_average = pressure_area / polygon_area
                force = tuple(-pressure_area * component for component in normal)
                moment = tuple(-component for component in _cross(position_pressure, normal))
                external_average = pressure_average + internal_pressure
                depth = max(0.0, waterline - centroid[2])
                method = "polygon_integrated_linear_pressure"
                pressure_value = pressure_average
                integration_centroid = (
                    tuple(value / pressure_area for value in position_pressure)
                    if abs(pressure_area) > 1e-12 else list(centroid)
                )
                panel_extra = {
                    "integration_method": method,
                    "pressure_resultant_centroid_m": list(integration_centroid),
                    "vertex_differential_pressures_pa": vertex_pressures,
                }
            else:
                depth = max(0.0, waterline - centroid[2])
                external_average = density * gravity * depth
                pressure_value = external_average - internal_pressure
                force = tuple(-pressure_value * area * component for component in normal)
                moment = _cross(centroid, force)
                panel_extra = {"integration_method": "centroid_uniform_pressure"}

            differential_average = pressure_value
            for axis in range(3):
                total_force[axis] += force[axis]
                total_moment[axis] += moment[axis]
            total_area += area
            max_external_pressure = max(max_external_pressure, external_average)
            panel_results.append({
                "panel_id": panel_id,
                "area_m2": area,
                "centroid_m": list(centroid),
                "depth_below_waterline_m": depth,
                "external_hydrostatic_pressure_pa": external_average,
                "internal_gauge_pressure_pa": internal_pressure,
                "differential_pressure_pa": differential_average,
                "force_xyz_n": list(force),
                "moment_about_origin_xyz_nm": list(moment),
                "loading_direction": (
                    "inward" if differential_average > 0.0
                    else "outward" if differential_average < 0.0 else "zero"
                ),
                **panel_extra,
            })

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="screening_only",
            values={
                "panel_count": len(panel_results),
                "total_panel_area_m2": total_area,
                "maximum_external_hydrostatic_pressure_pa": max_external_pressure,
                "total_force_xyz_n": total_force,
                "total_moment_about_origin_xyz_nm": total_moment,
                "panels": panel_results,
            },
            units={
                "panel_count": "count", "total_panel_area_m2": "m^2",
                "maximum_external_hydrostatic_pressure_pa": "Pa",
                "total_force_xyz_n": "N", "total_moment_about_origin_xyz_nm": "N*m",
                "panels": "structured",
            },
            method="signed_hydrostatic_panel_loads_with_optional_exact_linear_pressure_polygon_integration",
            assumptions=[
                "Waterline is horizontal; water density, gravity and internal gauge pressure are uniform.",
                "Outward normals are unit vectors; positive external-minus-internal pressure acts inward.",
                "Polygon mode assumes a convex planar polygon with consistently ordered vertices and pressure varying linearly with depth.",
                "Polygon panels crossing the waterline must be split at the waterline before analysis.",
                "Centroid-only panels retain the legacy uniform-pressure approximation.",
            ],
            warnings=[
                "This is a pressure-load generator, not a structural stress or scantling solver.",
                "Panel normals and polygon winding must be verified against the actual hull surface.",
                "Above-water panels have zero external hydrostatic pressure; internal gauge pressure still acts.",
            ],
            limitations=[
                "Polygon integration supports convex planar polygons only; non-convex polygons must be subdivided.",
                "No mesh connectivity, curved-surface integration, trim, heel, acceleration, waves, slamming, impact or grounding.",
                "No shell, laminate, stiffener, frame, bulkhead, joint or global hull-girder stress analysis.",
                "No hydrostatic equilibrium, buoyancy-volume integration or FEM boundary-condition coupling.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
