"""Preliminary external-pressure screening for a cylindrical ROV pressure housing.

This deliberately uses transparent thin-wall membrane stresses and an ideal
long-cylinder elastic-buckling estimate. It is not a pressure-vessel code
calculation, finite-length shell analysis, end-cap design, or certification.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


class ROVPressureHousingSolver:
    """Screen a straight cylindrical housing under uniform external water pressure."""

    name = "YJ64 ROV cylindrical pressure-housing screening"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "rov.pressure_housing_cylinder_screen"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")

        p = request.parameters
        geometry = p.get("geometry") or {}
        conditions = p.get("operating_conditions") or {}
        material = p.get("material") or {}

        diameter = _number(geometry.get("outer_diameter_m"), "outer_diameter_m", minimum=1e-9)
        thickness = _number(geometry.get("wall_thickness_m"), "wall_thickness_m", minimum=1e-9)
        if 2.0 * thickness >= diameter:
            raise ValueError("wall_thickness_m must be less than half the outer diameter")
        thickness_ratio = thickness / diameter
        if thickness_ratio > 0.10:
            raise ValueError(
                "thin-wall screening is limited to wall_thickness_m / outer_diameter_m <= 0.10"
            )

        depth = _number(conditions.get("external_water_depth_m"), "external_water_depth_m", minimum=0.0)
        density = _number(conditions.get("water_density_kg_m3", 1025.0), "water_density_kg_m3", minimum=1e-9)
        gravity = _number(conditions.get("gravity_m_s2", 9.80665), "gravity_m_s2", minimum=1e-9)
        internal_gauge = _number(conditions.get("internal_gauge_pressure_pa", 0.0), "internal_gauge_pressure_pa")
        external_gauge = density * gravity * depth
        differential = external_gauge - internal_gauge
        if differential <= 0.0:
            raise ValueError(
                "external differential pressure must be positive; this solver does not screen internal-pressure loading"
            )

        youngs_modulus = _number(material.get("youngs_modulus_pa"), "youngs_modulus_pa", minimum=1e-9)
        poisson = _number(material.get("poisson_ratio"), "poisson_ratio")
        if not 0.0 < poisson < 0.5:
            raise ValueError("poisson_ratio must be between 0 and 0.5")
        allowable_vm = _number(
            material.get("allowable_von_mises_stress_pa"),
            "allowable_von_mises_stress_pa",
            minimum=1e-9,
        )
        knockdown = _number(
            conditions.get("buckling_imperfection_factor"),
            "buckling_imperfection_factor",
            minimum=1e-9,
        )
        if knockdown > 1.0:
            raise ValueError("buckling_imperfection_factor must be <= 1.0")
        safety_factor = _number(
            conditions.get("design_factor_of_safety", 2.0),
            "design_factor_of_safety",
            minimum=1.0,
        )

        mean_diameter = diameter - thickness
        hoop_stress = -differential * mean_diameter / (2.0 * thickness)
        axial_stress = -differential * mean_diameter / (4.0 * thickness)
        von_mises = math.sqrt(
            hoop_stress**2 + axial_stress**2 - hoop_stress * axial_stress
        )
        allowable_design_stress = allowable_vm / safety_factor
        stress_utilization = von_mises / allowable_design_stress

        ideal_elastic_buckling_pressure = (
            2.0 * youngs_modulus
            / math.sqrt(3.0 * (1.0 - poisson**2))
            * (thickness / mean_diameter) ** 3
        )
        design_buckling_pressure = (
            ideal_elastic_buckling_pressure * knockdown / safety_factor
        )
        buckling_utilization = differential / design_buckling_pressure

        inner_diameter = diameter - 2.0 * thickness
        end_cap_resultant = differential * math.pi * inner_diameter**2 / 4.0
        preliminary_status = (
            "within_preliminary_screen"
            if stress_utilization <= 1.0 and buckling_utilization <= 1.0
            else "exceeds_preliminary_screen"
        )

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="screening_only",
            values={
                "external_hydrostatic_gauge_pressure_pa": external_gauge,
                "internal_gauge_pressure_pa": internal_gauge,
                "external_differential_pressure_pa": differential,
                "mean_diameter_m": mean_diameter,
                "inner_diameter_m": inner_diameter,
                "hoop_compressive_stress_pa": abs(hoop_stress),
                "axial_compressive_stress_pa": abs(axial_stress),
                "von_mises_membrane_stress_pa": von_mises,
                "allowable_von_mises_stress_pa": allowable_vm,
                "design_factor_of_safety": safety_factor,
                "stress_utilization": stress_utilization,
                "ideal_long_cylinder_elastic_buckling_pressure_pa": ideal_elastic_buckling_pressure,
                "buckling_imperfection_factor": knockdown,
                "design_buckling_pressure_pa": design_buckling_pressure,
                "buckling_utilization": buckling_utilization,
                "end_cap_resultant_force_n": end_cap_resultant,
                "preliminary_status": preliminary_status,
            },
            units={
                "external_hydrostatic_gauge_pressure_pa": "Pa",
                "internal_gauge_pressure_pa": "Pa",
                "external_differential_pressure_pa": "Pa",
                "mean_diameter_m": "m",
                "inner_diameter_m": "m",
                "hoop_compressive_stress_pa": "Pa",
                "axial_compressive_stress_pa": "Pa",
                "von_mises_membrane_stress_pa": "Pa",
                "allowable_von_mises_stress_pa": "Pa",
                "design_factor_of_safety": "dimensionless",
                "stress_utilization": "dimensionless",
                "ideal_long_cylinder_elastic_buckling_pressure_pa": "Pa",
                "buckling_imperfection_factor": "dimensionless",
                "design_buckling_pressure_pa": "Pa",
                "buckling_utilization": "dimensionless",
                "end_cap_resultant_force_n": "N",
                "preliminary_status": "category",
            },
            method="hydrostatic_differential_pressure_thin_wall_membrane_stress_and_knocked_down_ideal_long_cylinder_buckling_screen",
            assumptions=[
                "External water pressure is hydrostatic and uniform at the specified depth.",
                "Internal pressure is supplied as gauge pressure relative to the surrounding atmosphere.",
                "The cylindrical shell is circular, uniform, isotropic, thin-walled and initially geometrically perfect before applying the user-supplied buckling imperfection factor.",
                "Membrane stresses use the mean cylinder diameter; the ideal elastic buckling expression is for a long cylindrical shell.",
                "The design factor of safety is applied to both supplied allowable stress and knockdown-adjusted ideal buckling pressure.",
                "End-cap resultant is the pressure differential multiplied by the projected internal circular area; end-cap structural strength is not calculated.",
            ],
            warnings=[
                "screening_only: an ideal long-cylinder buckling formula is highly sensitive to ovality, dents, thickness variation, residual stress, cut-outs, penetrators, supports and end constraints.",
                "The buckling imperfection factor must be justified by applicable test data, a validated shell method or a qualified engineer; it is not inferred by this solver.",
                "A result within this preliminary screen is not proof of pressure-housing safety or a permissible operating depth.",
            ],
            limitations=[
                "No finite-length shell solution, nonlinear buckling, geometric imperfections, local penetrator/cut-out analysis or external-pressure code compliance.",
                "No end-cap, flange, bolt, seal, window, connector, cable penetrator, weld, adhesive or joint strength analysis.",
                "No fatigue, cyclic pressure, impact, corrosion, galvanic effects, material ageing, manufacturing tolerances or proof-test model.",
                "No composite/orthotropic laminate or sandwich-shell analysis; isotropic elastic material properties are assumed.",
                "No thermal gradient, transient pressure, dynamic water impact or pressure variation along an inclined/accelerating vehicle.",
                "No safety certification; validate with detailed shell analysis, material/process evidence, inspection and controlled proof/leak testing.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
