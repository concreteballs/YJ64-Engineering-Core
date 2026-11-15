"""Low-order catamaran hydrostatics from station-based hull envelopes.

This is a preliminary geometric displacement estimate, not a stability,
seakeeping, resistance, or class-rule calculation.
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


def _submerged_polygon_area(points: list[tuple[float, float]], waterline: float) -> float:
    """Clip a transverse polygon to z <= waterline and return its area."""
    clipped: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:] + points[:1]):
        z0, z1 = start[1], end[1]
        inside0, inside1 = z0 <= waterline, z1 <= waterline
        if inside0:
            clipped.append(start)
        if inside0 != inside1:
            fraction = (waterline - z0) / (z1 - z0)
            clipped.append((start[0] + fraction * (end[0] - start[0]), waterline))
    if len(clipped) < 3:
        return 0.0
    twice_area = sum(
        clipped[i][0] * clipped[(i + 1) % len(clipped)][1]
        - clipped[(i + 1) % len(clipped)][0] * clipped[i][1]
        for i in range(len(clipped))
    )
    return abs(twice_area) * 0.5


def _hull_volume(hull: dict[str, Any], waterline: float) -> float:
    stations = hull.get("stations")
    if not isinstance(stations, list) or len(stations) < 3:
        raise ValueError("each hull requires at least three stations")
    xs: list[float] = []
    areas: list[float] = []
    chine_fraction = _number(hull.get("chine_fraction", 0.72), "chine_fraction")
    if not 0.1 <= chine_fraction <= 0.95:
        raise ValueError("chine_fraction must be between 0.1 and 0.95")
    for index, station in enumerate(stations):
        if not isinstance(station, dict):
            raise TypeError("hull stations must be objects")
        x = _number(station.get("x_m"), f"stations[{index}].x_m")
        half_beam = _number(station.get("half_beam_m"), "half_beam_m")
        keel = _number(station.get("keel_z_m"), "keel_z_m")
        chine = _number(station.get("chine_z_m"), "chine_z_m")
        deck = _number(station.get("deck_z_m"), "deck_z_m")
        if half_beam <= 0 or not keel < chine < deck:
            raise ValueError("invalid hull station dimensions or vertical ordering")
        if xs and x <= xs[-1]:
            raise ValueError("station x_m values must be strictly increasing")
        xs.append(x)
        b = half_beam
        polygon = [
            (0.0, keel), (b * chine_fraction, chine), (b, deck),
            (-b, deck), (-b * chine_fraction, chine),
        ]
        areas.append(_submerged_polygon_area(polygon, waterline))
    return sum(
        (xs[i + 1] - xs[i]) * (areas[i] + areas[i + 1]) * 0.5
        for i in range(len(xs) - 1)
    )


class CatamaranHydrostaticsSolver:
    """Estimate twin-hull displacement at design and maximum waterlines."""

    name = "YJ64 catamaran hydrostatics screening"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "hydrostatics.catamaran_displacement"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        hulls = p.get("hulls")
        if not isinstance(hulls, list) or len(hulls) != 2:
            raise ValueError("hulls must contain exactly two hull geometry objects")
        design_wl = _number(p.get("design_waterline_z_m"), "design_waterline_z_m")
        max_wl = _number(p.get("maximum_waterline_z_m"), "maximum_waterline_z_m")
        density = _number(p.get("water_density_kg_m3", 1025.0), "water_density_kg_m3")
        if max_wl <= design_wl:
            raise ValueError("maximum_waterline_z_m must be above design_waterline_z_m")
        if density <= 0:
            raise ValueError("water_density_kg_m3 must be positive")
        design_volume = sum(_hull_volume(h, design_wl) for h in hulls)
        max_volume = sum(_hull_volume(h, max_wl) for h in hulls)
        if design_volume <= 0 or max_volume <= design_volume:
            raise ValueError("waterlines must produce positive increasing displaced volumes")
        design_mass = design_volume * density
        max_mass = max_volume * density
        return AnalysisResult(
            analysis_type=request.analysis_type, status="screening_only",
            values={
                "design_displacement_volume_m3": design_volume,
                "design_displacement_mass_kg": design_mass,
                "maximum_displacement_volume_m3": max_volume,
                "maximum_displacement_mass_kg": max_mass,
                "reserve_buoyancy_volume_m3": max_volume - design_volume,
                "reserve_buoyancy_fraction_of_max": (max_volume - design_volume) / max_volume,
                "water_density_kg_m3": density,
            },
            units={
                "design_displacement_volume_m3": "m^3",
                "design_displacement_mass_kg": "kg",
                "maximum_displacement_volume_m3": "m^3",
                "maximum_displacement_mass_kg": "kg",
                "reserve_buoyancy_volume_m3": "m^3",
                "reserve_buoyancy_fraction_of_max": "fraction",
                "water_density_kg_m3": "kg/m^3",
            },
            method="transverse_polygon_clipping_and_longitudinal_trapezoidal_integration_per_hull",
            assumptions=[
                "Exactly two independent station-based hull envelopes are integrated.",
                "Each section is represented by the five-point chine polygon used by the current hull geometry.",
                "The waterline is horizontal and both hulls use the same water density.",
                "Longitudinal sectional areas are integrated with the trapezoidal rule.",
            ],
            warnings=[
                "screening_only: the current hull envelope is a simplified outer surface; results depend on station density and geometry fidelity.",
                "Maximum waterline is a user-defined geometric limit, not a certified safe loading limit.",
            ],
            limitations=[
                "No trim, heel, transverse waterplane coupling, damaged stability, downflooding, wave response or dynamic loads.",
                "No regulatory freeboard, reserve buoyancy, stability-curve or load-line compliance check.",
                "No appendage displacement, hull deformation, skin thickness or interior volume deduction.",
                "Not valid for foiling flight condition; use a separate transient hydrodynamic model there.",
            ],
            solver_name=self.name, solver_version=self.version,
        )
