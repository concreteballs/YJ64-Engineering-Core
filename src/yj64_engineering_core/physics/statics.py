"""Small, auditable analytical calculations using SI units."""

from __future__ import annotations

from ..models import AnalysisResult, MaterialProperties


def calculate_axial_member(
    *,
    force_n: float,
    area_m2: float,
    length_m: float,
    material: MaterialProperties,
) -> AnalysisResult:
    """Estimate stress and elastic elongation for a straight axial member.

    Assumptions:
    - uniform cross-section and homogeneous material;
    - linear-elastic response;
    - load is concentric and purely axial;
    - small deformation;
    - no buckling, fatigue, stress concentrations, joints, or thermal effects.

    This is a screening calculation, not a complete component verification.
    """
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")
    if length_m <= 0:
        raise ValueError("length_m must be positive")

    stress_pa = abs(force_n) / area_m2
    strain = stress_pa / material.youngs_modulus_pa
    elongation_m = strain * length_m
    safety_factor = material.allowable_stress_pa / stress_pa if stress_pa else float("inf")

    warnings: list[str] = []
    if stress_pa > material.allowable_stress_pa:
        warnings.append("Calculated axial stress exceeds the supplied allowable stress.")
    if safety_factor < 1.0:
        status = "fail_screening"
    else:
        status = "screening_only"

    return AnalysisResult(
        analysis_type="axial_member",
        status=status,
        values={
            "force_n": force_n,
            "stress_pa": stress_pa,
            "strain": strain,
            "elongation_m": elongation_m,
            "safety_factor_vs_allowable": safety_factor,
        },
        units={
            "force_n": "N",
            "stress_pa": "Pa",
            "strain": "dimensionless",
            "elongation_m": "m",
            "safety_factor_vs_allowable": "dimensionless",
        },
        method="linear_elastic_axial_stress",
        assumptions=[
            "Uniform cross-section",
            "Homogeneous, isotropic, linear-elastic material",
            "Concentric axial load",
            "Small deformation",
        ],
        warnings=warnings,
        limitations=[
            "Does not check buckling, fatigue, fracture, joints, stress concentrations, or thermal loads.",
            "Material allowable stress must come from a verified source and appropriate design standard.",
            "Not suitable by itself for safety-critical design approval.",
        ],
        solver_name="YJ64 reference statics solver",
        solver_version="0.1.0",
    )
