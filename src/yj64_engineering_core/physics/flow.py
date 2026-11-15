"""Shared low-order steady-flow calculations for aerodynamic and hydrodynamic screening.

These coefficient-based models are deliberately not CFD solvers. They provide
transparent force estimates when the user supplies validated coefficients.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _finite_number(values: dict[str, Any], name: str, *, positive: bool = False) -> float:
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def coefficient_flow_result(
    request: AnalysisRequest,
    *,
    analysis_type: str,
    method: str,
    solver_name: str,
    limitations: list[str],
) -> AnalysisResult:
    """Calculate forces from dynamic pressure and supplied dimensionless coefficients."""
    p = request.parameters
    geometry = p.get("geometry")
    conditions = p.get("operating_conditions")
    if not isinstance(geometry, dict):
        raise TypeError("geometry must be an object")
    if not isinstance(conditions, dict):
        raise TypeError("operating_conditions must be an object")

    area = _finite_number(geometry, "reference_area_m2", positive=True)
    length = _finite_number(geometry, "characteristic_length_m", positive=True)
    speed = _finite_number(conditions, "flow_speed_m_s")
    density = _finite_number(conditions, "fluid_density_kg_m3", positive=True)
    viscosity = _finite_number(conditions, "dynamic_viscosity_pa_s", positive=True)
    lift_coefficient = _finite_number(conditions, "lift_coefficient")
    drag_coefficient = _finite_number(conditions, "drag_coefficient")
    side_coefficient = _finite_number(conditions, "side_force_coefficient")
    if speed < 0:
        raise ValueError("flow_speed_m_s cannot be negative")
    if drag_coefficient < 0:
        raise ValueError("drag_coefficient cannot be negative")

    dynamic_pressure = 0.5 * density * speed * speed
    lift = dynamic_pressure * area * lift_coefficient
    drag = dynamic_pressure * area * drag_coefficient
    side_force = dynamic_pressure * area * side_coefficient
    reynolds = density * speed * length / viscosity

    warnings = [
        "Coefficient-based steady-flow screening only; coefficients are user-supplied and are not predicted by this model.",
        "This result is not a CFD solution and does not resolve flow separation, free-surface effects, waves, ventilation, or transient loads.",
    ]
    if speed == 0:
        warnings.append("Zero flow speed produces zero dynamic pressure and zero calculated forces.")

    return AnalysisResult(
        analysis_type=analysis_type,
        status="screening_only",
        values={
            "dynamic_pressure_pa": dynamic_pressure,
            "lift_force_n": lift,
            "drag_force_n": drag,
            "side_force_n": side_force,
            "reynolds_number": reynolds,
            "reference_area_m2": area,
            "characteristic_length_m": length,
            "flow_speed_m_s": speed,
            "fluid_density_kg_m3": density,
            "lift_coefficient": lift_coefficient,
            "drag_coefficient": drag_coefficient,
            "side_force_coefficient": side_coefficient,
        },
        units={
            "dynamic_pressure_pa": "Pa",
            "lift_force_n": "N",
            "drag_force_n": "N",
            "side_force_n": "N",
            "reynolds_number": "dimensionless",
            "reference_area_m2": "m^2",
            "characteristic_length_m": "m",
            "flow_speed_m_s": "m/s",
            "fluid_density_kg_m3": "kg/m^3",
            "lift_coefficient": "dimensionless",
            "drag_coefficient": "dimensionless",
            "side_force_coefficient": "dimensionless",
        },
        method=method,
        assumptions=[
            "Steady, incompressible flow.",
            "Uniform approach flow at the supplied speed and density.",
            "Constant user-supplied dimensionless force coefficients.",
            "Forces are scalar components in the chosen reference axes; orientation transforms are not performed.",
        ],
        warnings=warnings,
        limitations=limitations,
        solver_name=solver_name,
        solver_version="0.1.0",
    )
