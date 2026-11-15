"""Comparative hull-material mass, cost and maintenance screening.

Layer properties and commercial rates are explicit inputs. This module does
not size scantlings or establish structural equivalence between materials.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


SUPPORTED_FAMILIES = {
    "aluminium",
    "glass_fiber_composite",
    "carbon_fiber_composite",
    "reinforced_concrete",
}


def _number(value: Any, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return result


def _layer_areal_mass(layer: dict[str, Any], index: int) -> float:
    label = f"layers[{index}]"
    if "areal_mass_kg_m2" in layer:
        return _number(layer["areal_mass_kg_m2"], f"{label}.areal_mass_kg_m2")
    if "thickness_m" not in layer or "density_kg_m3" not in layer:
        raise ValueError(
            f"{label} requires areal_mass_kg_m2 or both thickness_m and density_kg_m3"
        )
    thickness = _number(layer["thickness_m"], f"{label}.thickness_m")
    density = _number(layer["density_kg_m3"], f"{label}.density_kg_m3", minimum=0.000001)
    return thickness * density


class HullMaterialScreeningSolver:
    """Compare explicitly specified hull build-ups without assuming scantlings."""

    name = "YJ64 hull material comparison screening"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "hull.material_screen"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        conditions = request.parameters.get("operating_conditions") or {}
        alternatives = conditions.get("alternatives")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError("operating_conditions.alternatives must be a non-empty array")

        results = []
        for index, alternative in enumerate(alternatives):
            if not isinstance(alternative, dict):
                raise TypeError("each hull material alternative must be an object")
            name = str(alternative.get("name", f"alternative_{index + 1}"))
            family = alternative.get("material_family")
            if family not in SUPPORTED_FAMILIES:
                raise ValueError(
                    f"unsupported material_family {family!r}; supported: "
                    + ", ".join(sorted(SUPPORTED_FAMILIES))
                )
            construction = alternative.get("construction_type", "monolithic")
            if construction not in {"monolithic", "sandwich", "honeycomb"}:
                raise ValueError("construction_type must be monolithic, sandwich or honeycomb")
            area = _number(alternative.get("structural_area_m2"), f"{name}.structural_area_m2", minimum=0.000001)
            layers = alternative.get("layers")
            if not isinstance(layers, list) or not layers:
                raise ValueError(f"{name}.layers must be a non-empty array")
            layer_masses = []
            for layer_index, layer in enumerate(layers):
                if not isinstance(layer, dict):
                    raise TypeError("each layer must be an object")
                layer_name = str(layer.get("name", f"layer_{layer_index + 1}"))
                areal_mass = _layer_areal_mass(layer, layer_index)
                layer_masses.append({
                    "name": layer_name,
                    "areal_mass_kg_m2": areal_mass,
                    "mass_kg": areal_mass * area,
                })
            secondary_mass = _number(
                alternative.get("secondary_mass_kg", 0.0),
                f"{name}.secondary_mass_kg",
            )
            shell_mass = sum(item["mass_kg"] for item in layer_masses)
            installed_mass = shell_mass + secondary_mass
            entry: dict[str, Any] = {
                "name": name,
                "material_family": family,
                "construction_type": construction,
                "structural_area_m2": area,
                "layer_masses": layer_masses,
                "shell_layer_mass_kg": shell_mass,
                "secondary_mass_kg": secondary_mass,
                "installed_hull_build_up_mass_kg": installed_mass,
                "installed_areal_mass_kg_m2": installed_mass / area,
            }
            material_rate = alternative.get("material_cost_eur_m2")
            manufacturing_rate = alternative.get("manufacturing_cost_eur_m2")
            if material_rate is not None:
                rate = _number(material_rate, f"{name}.material_cost_eur_m2")
                entry["material_cost_eur"] = rate * area
            if manufacturing_rate is not None:
                rate = _number(manufacturing_rate, f"{name}.manufacturing_cost_eur_m2")
                entry["manufacturing_cost_eur"] = rate * area
            if material_rate is not None or manufacturing_rate is not None:
                entry["known_build_cost_eur"] = entry.get("material_cost_eur", 0.0) + entry.get("manufacturing_cost_eur", 0.0)
            maintenance = alternative.get("annual_maintenance_cost_eur")
            if maintenance is not None:
                entry["annual_maintenance_cost_eur"] = _number(
                    maintenance, f"{name}.annual_maintenance_cost_eur"
                )
            interval = alternative.get("major_maintenance_interval_years")
            if interval is not None:
                entry["major_maintenance_interval_years"] = _number(
                    interval, f"{name}.major_maintenance_interval_years", minimum=0.000001
                )
            results.append(entry)

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="screening_only",
            values={"alternatives": results, "alternative_count": len(results)},
            units={"alternatives": "mixed", "alternative_count": "count"},
            method="explicit_layer_areal_mass_or_thickness_density_with_user_supplied_cost_and_maintenance_inputs",
            assumptions=[
                "Every alternative uses the same declared structural surface-area basis only when the caller supplies comparable areas.",
                "Layer mass is calculated from cured areal mass or thickness multiplied by supplied density.",
                "Secondary mass includes only items explicitly entered by the caller.",
                "Costs and maintenance values are user/supplier estimates in EUR, not market-price lookups.",
            ],
            warnings=[
                "screening_only: equal area does not mean equal strength, stiffness, fatigue life, impact resistance or safety.",
                "Do not compare alternatives as structurally equivalent until each build-up has been independently sized and verified.",
                "Composite skin areal mass should represent the cured laminate; include resin, adhesive, inserts, coatings and local reinforcements exactly once.",
                "Honeycomb/core properties and edge closures must be supplied explicitly; core mass alone does not establish panel performance.",
            ],
            limitations=[
                "No laminate theory, fibre volume fraction, orthotropic stiffness, buckling, impact, fatigue, fire or joint analysis.",
                "No aluminium weld heat-affected-zone, corrosion, galvanic isolation or fatigue assessment.",
                "No concrete cracking, reinforcement design, shrinkage, creep, water ingress or reinforcement corrosion model.",
                "No lifecycle discounting, downtime, repair logistics, antifouling or coating renewal model.",
                "No scantling optimisation or classification-society compliance.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
