"""Sail fabric and construction mass/stiffness screening.

The model distinguishes areal mass from bulk density and records anisotropic
membrane properties. It does not predict a deformed sail shape or certify
cloth, seams, stitching, attachments, or a complete sail structure.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _finite(mapping: dict[str, Any], key: str, *, required: bool = True) -> float | None:
    value = mapping.get(key)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{key} must be finite")
    return result


class SailMaterialSolver:
    """Estimate sail cloth mass and expose orthotropic membrane properties."""

    name = "YJ64 sail material and construction screening"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "sail.material_screen"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        geometry, material = p.get("geometry"), p.get("material")
        if not isinstance(geometry, dict) or not isinstance(material, dict):
            raise TypeError("geometry and material must be objects")
        area = _finite(geometry, "sail_area_m2")
        assert area is not None
        if area <= 0:
            raise ValueError("sail_area_m2 must be positive")

        areal = _finite(material, "areal_density_kg_m2", required=False)
        bulk_density = _finite(material, "bulk_density_kg_m3", required=False)
        thickness = _finite(material, "thickness_m", required=False)
        if areal is None:
            if bulk_density is None or thickness is None:
                raise ValueError("provide areal_density_kg_m2 or both bulk_density_kg_m3 and thickness_m")
            if bulk_density <= 0 or thickness <= 0:
                raise ValueError("bulk density and thickness must be positive")
            areal = bulk_density * thickness
        if areal <= 0:
            raise ValueError("areal_density_kg_m2 must be positive")

        seam_fraction = _finite(material, "seam_and_overlap_fraction", required=False)
        seam_fraction = 0.0 if seam_fraction is None else seam_fraction
        reinforcement_mass = _finite(material, "reinforcement_mass_kg", required=False)
        reinforcement_mass = 0.0 if reinforcement_mass is None else reinforcement_mass
        hardware_mass = _finite(material, "hardware_mass_kg", required=False)
        hardware_mass = 0.0 if hardware_mass is None else hardware_mass
        if seam_fraction < 0 or reinforcement_mass < 0 or hardware_mass < 0:
            raise ValueError("construction allowances and added masses cannot be negative")

        warp = _finite(material, "warp_tensile_stiffness_n_m", required=False)
        weft = _finite(material, "weft_tensile_stiffness_n_m", required=False)
        shear = _finite(material, "in_plane_shear_stiffness_n_m", required=False)
        warp_strength = _finite(material, "warp_tensile_strength_n_m", required=False)
        weft_strength = _finite(material, "weft_tensile_strength_n_m", required=False)
        creep = _finite(material, "long_term_creep_strain_fraction", required=False)
        for key, value in (("warp_tensile_stiffness_n_m", warp), ("weft_tensile_stiffness_n_m", weft),
                           ("in_plane_shear_stiffness_n_m", shear), ("warp_tensile_strength_n_m", warp_strength),
                           ("weft_tensile_strength_n_m", weft_strength)):
            if value is not None and value <= 0:
                raise ValueError(f"{key} must be positive")
        if creep is not None and not 0 <= creep < 1:
            raise ValueError("long_term_creep_strain_fraction must be in [0, 1)")

        cloth_area = area * (1.0 + seam_fraction)
        cloth_mass = cloth_area * areal
        total_mass = cloth_mass + reinforcement_mass + hardware_mass
        values = {
            "sail_plan_area_m2": area,
            "estimated_fabric_area_m2": cloth_area,
            "material_areal_density_kg_m2": areal,
            "fabric_mass_kg": cloth_mass,
            "reinforcement_mass_kg": reinforcement_mass,
            "hardware_mass_kg": hardware_mass,
            "estimated_total_sail_mass_kg": total_mass,
        }
        units = {
            "sail_plan_area_m2": "m^2", "estimated_fabric_area_m2": "m^2",
            "material_areal_density_kg_m2": "kg/m^2", "fabric_mass_kg": "kg",
            "reinforcement_mass_kg": "kg", "hardware_mass_kg": "kg",
            "estimated_total_sail_mass_kg": "kg",
        }
        optional = {
            "warp_tensile_stiffness_n_m": warp, "weft_tensile_stiffness_n_m": weft,
            "in_plane_shear_stiffness_n_m": shear, "warp_tensile_strength_n_m": warp_strength,
            "weft_tensile_strength_n_m": weft_strength, "long_term_creep_strain_fraction": creep,
        }
        for key, value in optional.items():
            if value is not None:
                values[key] = value
                units[key] = "N/m" if key.endswith("_n_m") else "strain"

        warnings = [
            "screening_only: mass estimate uses supplied material and construction allowances; verify against a sailmaker's bill of materials.",
            "No membrane stress, seam strength, shape retention, fatigue life or aeroelastic deformation is calculated.",
        ]
        if warp is None or weft is None:
            warnings.append("Anisotropic warp/weft stiffness is incomplete; shape-retention assessment is not possible.")
        return AnalysisResult(
            analysis_type=request.analysis_type, status="screening_only",
            values=values, units=units,
            method="areal_mass_with_construction_allowances_and_orthotropic_property_capture",
            assumptions=[
                "Areal density is mass per actual fabric area, not bulk material density.",
                "Fabric area equals plan area multiplied by (1 + seam_and_overlap_fraction).",
                "Reinforcement and hardware masses are added as separate user-supplied allowances.",
                "Warp and weft properties are retained separately because woven/laminated sail materials are direction-dependent.",
            ],
            warnings=warnings,
            limitations=[
                "No universal material density is inferred from sail size or sail type; select data for the actual cloth/laminate and construction.",
                "Panel layout, membrane orientation, seams, load paths, batten pockets, luff/leech reinforcement and local patches require design-specific inputs.",
                "Stiffness values are recorded but not converted into a predicted flying shape; nonlinear orthotropic membrane analysis and validated load cases are required.",
                "Strength values are material-level inputs only and do not establish seam, attachment or complete-sail safety factors.",
            ],
            solver_name=self.name, solver_version=self.version,
        )
