"""Sail aerodynamic screening from an explicit, tabulated coefficient polar.

This is a low-order lifting-surface model. It interpolates supplied section or
sail-system polars and adds a classical finite-span induced-drag correction.
It does not generate the polar or model flexible-sail/rig interaction.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _number(mapping: dict[str, Any], key: str, *, positive: bool = False) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    result = float(value)
    if positive and result <= 0.0:
        raise ValueError(f"{key} must be positive")
    return result


def _polar_points(raw: Any) -> list[tuple[float, float, float, float]]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("polar_points must contain at least two coefficient rows")
    parsed: list[tuple[float, float, float, float]] = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            raise TypeError(f"polar_points[{index}] must be an object")
        alpha = _number(row, "alpha_deg")
        cl = _number(row, "cl")
        cd = _number(row, "cd")
        cm = _number(row, "cm")
        if cd < 0.0:
            raise ValueError(f"polar_points[{index}].cd cannot be negative")
        if parsed and alpha <= parsed[-1][0]:
            raise ValueError("polar alpha_deg values must be strictly increasing")
        parsed.append((alpha, cl, cd, cm))
    return parsed


def interpolate_sail_polar(
    points: list[tuple[float, float, float, float]], alpha_deg: float
) -> tuple[float, float, float]:
    """Linearly interpolate CL, CD and CM; extrapolation is deliberately forbidden."""
    if alpha_deg < points[0][0] or alpha_deg > points[-1][0]:
        raise ValueError(
            f"angle_of_attack_deg={alpha_deg:g} is outside the supplied polar "
            f"range [{points[0][0]:g}, {points[-1][0]:g}] degrees"
        )
    for left, right in zip(points, points[1:]):
        if left[0] <= alpha_deg <= right[0]:
            fraction = (alpha_deg - left[0]) / (right[0] - left[0])
            return tuple(
                left[column] + fraction * (right[column] - left[column])
                for column in (1, 2, 3)
            )
    return points[-1][1], points[-1][2], points[-1][3]


class SailAerodynamicsSolver:
    """Calculate sail forces from a supplied polar and apparent-wind state.

    Coordinate convention: X is forward, Y is starboard. Apparent wind angle
    is the direction the wind comes FROM, measured from the bow; positive is
    starboard. Positive CL acts 90 degrees counter-clockwise from the airflow
    direction. Positive CM is a nose-up pitching moment about quarter chord.
    """

    name = "YJ64 sail polar aerodynamics"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "aerodynamics.sail_polar"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        parameters = request.parameters
        geometry = parameters.get("geometry")
        conditions = parameters.get("operating_conditions")
        if not isinstance(geometry, dict):
            raise TypeError("geometry must be an object")
        if not isinstance(conditions, dict):
            raise TypeError("operating_conditions must be an object")

        area = _number(geometry, "sail_area_m2", positive=True)
        span = _number(geometry, "span_m", positive=True)
        chord = _number(geometry, "mean_chord_m", positive=True)
        speed = _number(conditions, "apparent_wind_speed_m_s")
        density = _number(conditions, "air_density_kg_m3", positive=True)
        viscosity = _number(conditions, "dynamic_viscosity_pa_s", positive=True)
        alpha = _number(conditions, "angle_of_attack_deg")
        awa_from = _number(conditions, "apparent_wind_from_angle_deg")
        efficiency = _number(conditions, "oswald_efficiency", positive=True)
        if speed < 0.0:
            raise ValueError("apparent_wind_speed_m_s cannot be negative")
        if efficiency > 1.0:
            raise ValueError("oswald_efficiency cannot exceed 1.0")

        polar = _polar_points(geometry.get("polar_points"))
        cl, cd_profile, cm = interpolate_sail_polar(polar, alpha)
        aspect_ratio = span * span / area
        cd_induced = cl * cl / (math.pi * efficiency * aspect_ratio)
        cd_total = cd_profile + cd_induced
        dynamic_pressure = 0.5 * density * speed * speed
        lift = dynamic_pressure * area * cl
        profile_drag = dynamic_pressure * area * cd_profile
        induced_drag = dynamic_pressure * area * cd_induced
        total_drag = profile_drag + induced_drag
        moment = dynamic_pressure * area * chord * cm
        reynolds = density * speed * chord / viscosity

        # Wind-from angle is converted to the direction in which air travels.
        flow_angle = math.radians(awa_from + 180.0)
        drag_x = total_drag * math.cos(flow_angle)
        drag_y = total_drag * math.sin(flow_angle)
        lift_x = -lift * math.sin(flow_angle)
        lift_y = lift * math.cos(flow_angle)
        force_x = drag_x + lift_x
        force_y = drag_y + lift_y

        warnings = [
            "screening_only: supplied polar is interpolated; this solver does not generate or validate aerodynamic coefficients.",
            "Finite-span induced drag uses a classical Oswald-efficiency correction; flexible sail shape, mast/rig interference and 3D separation are not resolved.",
            "Force axes use X forward and Y starboard; apparent wind angle is the direction wind comes from, positive to starboard.",
        ]
        if speed == 0.0:
            warnings.append("Zero apparent-wind speed produces zero aerodynamic forces and moment.")

        source = geometry.get("polar_source", "unspecified user-supplied polar")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("polar_source must be a non-empty string when supplied")

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="screening_only",
            values={
                "dynamic_pressure_pa": dynamic_pressure,
                "angle_of_attack_deg": alpha,
                "apparent_wind_from_angle_deg": awa_from,
                "lift_coefficient": cl,
                "profile_drag_coefficient": cd_profile,
                "induced_drag_coefficient": cd_induced,
                "total_drag_coefficient": cd_total,
                "pitching_moment_coefficient": cm,
                "aspect_ratio": aspect_ratio,
                "lift_force_n": lift,
                "profile_drag_force_n": profile_drag,
                "induced_drag_force_n": induced_drag,
                "total_drag_force_n": total_drag,
                "force_x_forward_n": force_x,
                "force_y_starboard_n": force_y,
                "aerodynamic_moment_nm": moment,
                "reynolds_number": reynolds,
                "sail_area_m2": area,
                "span_m": span,
                "mean_chord_m": chord,
            },
            units={
                "dynamic_pressure_pa": "Pa",
                "angle_of_attack_deg": "deg",
                "apparent_wind_from_angle_deg": "deg",
                "lift_coefficient": "dimensionless",
                "profile_drag_coefficient": "dimensionless",
                "induced_drag_coefficient": "dimensionless",
                "total_drag_coefficient": "dimensionless",
                "pitching_moment_coefficient": "dimensionless",
                "aspect_ratio": "dimensionless",
                "lift_force_n": "N",
                "profile_drag_force_n": "N",
                "induced_drag_force_n": "N",
                "total_drag_force_n": "N",
                "force_x_forward_n": "N",
                "force_y_starboard_n": "N",
                "aerodynamic_moment_nm": "N*m",
                "reynolds_number": "dimensionless",
                "sail_area_m2": "m^2",
                "span_m": "m",
                "mean_chord_m": "m",
            },
            method="tabulated_sail_polar_interpolation_with_finite_span_induced_drag",
            assumptions=[
                "Steady, incompressible apparent airflow with uniform density and speed.",
                "Lift, profile drag and quarter-chord moment coefficients are linearly interpolated between supplied polar rows.",
                "No extrapolation is permitted outside the supplied angle-of-attack polar range.",
                "Finite-span induced drag is estimated as CL^2/(pi*e*AR), with AR=span^2/sail_area.",
                "Polar source: " + source,
                "Positive pitching moment is defined as nose-up about the quarter-chord reference.",
            ],
            warnings=warnings,
            limitations=[
                "The polar must represent the relevant sail section or complete sail/rig configuration and Reynolds-number range.",
                "No automatic sail-shape generation, aeroelastic deformation, reefing, mast or standing-rig interference, wind gradient, gust response, dynamic stall or sail interaction.",
                "No automatic apparent-wind or sail-trim equilibrium; the operating point is supplied by the caller.",
                "No validated wind-tunnel or full-scale calibration is bundled with this solver.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
