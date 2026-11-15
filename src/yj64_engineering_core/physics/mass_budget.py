"""Vessel mass budget and loading ledger with tank fill states and CG.

This is a bookkeeping and first-moment model. It does not establish stability
or structural safety; those require the complete vessel geometry and loading
conditions.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


class VesselMassBudgetSolver:
    """Sum subsystem masses, tank loads, and longitudinal/transverse/vertical CG."""

    name = "YJ64 vessel mass budget"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "vessel.mass_budget"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        items = p.get("items", [])
        tanks = p.get("tanks", [])
        if not isinstance(items, list) or not isinstance(tanks, list):
            raise TypeError("items and tanks must be arrays")
        totals = {"structure": 0.0, "rig_sails": 0.0, "propulsion": 0.0,
                  "systems": 0.0, "interior": 0.0, "stores": 0.0, "other": 0.0}
        moments = [0.0, 0.0, 0.0]
        total = 0.0

        def add(mass: float, x: float, y: float, z: float, category: str) -> None:
            nonlocal total
            if mass < 0:
                raise ValueError("item mass cannot be negative")
            if category not in totals:
                raise ValueError(f"unsupported mass category: {category}")
            totals[category] += mass
            total += mass
            moments[0] += mass * x
            moments[1] += mass * y
            moments[2] += mass * z

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError("items must contain objects")
            add(_finite(item.get("mass_kg"), f"items[{index}].mass_kg"),
                _finite(item.get("x_m", 0.0), "x_m"),
                _finite(item.get("y_m", 0.0), "y_m"),
                _finite(item.get("z_m", 0.0), "z_m"),
                item.get("category", "other"))

        tank_mass_total = 0.0
        tank_results = []
        for index, tank in enumerate(tanks):
            if not isinstance(tank, dict):
                raise TypeError("tanks must contain objects")
            capacity = _finite(tank.get("capacity_m3"), "tank capacity_m3")
            fill = _finite(tank.get("fill_fraction", 1.0), "tank fill_fraction")
            fluid_density = _finite(tank.get("fluid_density_kg_m3"), "tank fluid_density_kg_m3")
            tare = _finite(tank.get("tank_and_fittings_mass_kg", 0.0), "tank_and_fittings_mass_kg")
            x, y, z = (_finite(tank.get(k, 0.0), k) for k in ("x_m", "y_m", "z_m"))
            if capacity < 0 or tare < 0 or fluid_density <= 0 or not 0 <= fill <= 1:
                raise ValueError("invalid tank capacity, tare, density or fill fraction")
            fluid_mass = capacity * fill * fluid_density
            tank_mass = fluid_mass + tare
            tank_mass_total += tank_mass
            add(tank_mass, x, y, z, tank.get("category", "systems"))
            tank_results.append({
                "name": str(tank.get("name", f"tank_{index + 1}")),
                "fluid_volume_m3": capacity * fill,
                "fluid_mass_kg": fluid_mass,
                "tank_and_fittings_mass_kg": tare,
                "total_loaded_mass_kg": tank_mass,
                "fill_fraction": fill,
            })

        if total <= 0:
            raise ValueError("total vessel mass must be positive")
        values: dict[str, Any] = {
            "total_mass_kg": total,
            "tank_loaded_mass_kg": tank_mass_total,
            "longitudinal_cg_x_m": moments[0] / total,
            "transverse_cg_y_m": moments[1] / total,
            "vertical_cg_z_m": moments[2] / total,
            "mass_by_category_kg": totals,
            "tank_loads": tank_results,
        }
        units = {
            "total_mass_kg": "kg", "tank_loaded_mass_kg": "kg",
            "longitudinal_cg_x_m": "m", "transverse_cg_y_m": "m",
            "vertical_cg_z_m": "m", "mass_by_category_kg": "kg",
            "tank_loads": "mixed",
        }
        warnings = ["screening_only: every component must be entered once; avoid double-counting tank fluid, machinery or outfitting masses."]
        limitations = [
            "No stability, trim, bending, slamming, structural margins or regulatory loading assessment.",
            "Tank liquid CG is approximated at the tank reference point; free-surface effects and changing CG with fill level are not modelled.",
            "The ledger is only as complete as its component list and supplied masses/coordinates.",
        ]
        capacity = p.get("design_displacement_limit_kg")
        if capacity is not None:
            limit = _finite(capacity, "design_displacement_limit_kg")
            if limit <= 0:
                raise ValueError("design_displacement_limit_kg must be positive")
            values["design_displacement_limit_kg"] = limit
            values["mass_margin_to_design_displacement_kg"] = limit - total
            values["payload_status"] = "within_mass_limit" if total <= limit else "over_mass_limit"
            units["design_displacement_limit_kg"] = "kg"
            units["mass_margin_to_design_displacement_kg"] = "kg"
            units["payload_status"] = "status"
        return AnalysisResult(
            analysis_type=request.analysis_type, status="screening_only",
            values=values, units=units,
            method="component_mass_ledger_tank_fill_and_first_moment_centre_of_gravity",
            assumptions=[
                "All component masses and coordinates are supplied in SI units.",
                "Tank fluid mass equals capacity multiplied by fill fraction and fluid density.",
                "Each component/tank is represented by a point mass at its supplied reference coordinate.",
            ],
            warnings=warnings, limitations=limitations,
            solver_name=self.name, solver_version=self.version,
        )
