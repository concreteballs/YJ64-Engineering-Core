"""True-wind to apparent-wind vector transformation in vessel axes."""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _value(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{key} must be finite")
    return result


class ApparentWindSolver:
    """Compute apparent airflow as true-air velocity minus vessel velocity.

    X is forward and Y is starboard. Wind direction is specified as the
    direction it comes FROM, measured from the bow and positive starboard.
    Vessel velocity is relative to the water/ground frame used for true wind.
    """

    name = "YJ64 apparent wind vector solver"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "aerodynamics.apparent_wind"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        c = request.parameters.get("operating_conditions")
        if not isinstance(c, dict):
            raise TypeError("operating_conditions must be an object")
        wind_speed = _value(c, "true_wind_speed_m_s")
        wind_from = _value(c, "true_wind_from_angle_deg")
        boat_x = _value(c, "vessel_velocity_x_forward_m_s")
        boat_y = _value(c, "vessel_velocity_y_starboard_m_s")
        if wind_speed < 0:
            raise ValueError("true_wind_speed_m_s cannot be negative")
        wind_to = math.radians(wind_from + 180.0)
        true_air_x = wind_speed * math.cos(wind_to)
        true_air_y = wind_speed * math.sin(wind_to)
        apparent_x = true_air_x - boat_x
        apparent_y = true_air_y - boat_y
        speed = math.hypot(apparent_x, apparent_y)
        wind_comes_from = math.degrees(math.atan2(-apparent_y, -apparent_x)) if speed else 0.0
        wind_comes_from = (wind_comes_from + 180.0) % 360.0 - 180.0
        return AnalysisResult(
            analysis_type=request.analysis_type, status="screening_only",
            values={
                "true_air_velocity_x_forward_m_s": true_air_x,
                "true_air_velocity_y_starboard_m_s": true_air_y,
                "apparent_air_velocity_x_forward_m_s": apparent_x,
                "apparent_air_velocity_y_starboard_m_s": apparent_y,
                "apparent_wind_speed_m_s": speed,
                "apparent_wind_from_angle_deg": wind_comes_from,
            },
            units={
                "true_air_velocity_x_forward_m_s": "m/s",
                "true_air_velocity_y_starboard_m_s": "m/s",
                "apparent_air_velocity_x_forward_m_s": "m/s",
                "apparent_air_velocity_y_starboard_m_s": "m/s",
                "apparent_wind_speed_m_s": "m/s",
                "apparent_wind_from_angle_deg": "deg",
            },
            method="vector_subtraction_true_air_velocity_minus_vessel_velocity",
            assumptions=[
                "True wind and vessel velocity are expressed in the same reference frame.",
                "Wind direction is the direction from which wind comes; positive angle is starboard from the bow.",
                "X is forward and Y is starboard.",
            ],
            warnings=["screening_only: validate wind reference (ground-relative versus water-relative) and current treatment for the intended sailing condition."],
            limitations=["No wind gradient, gust dynamics, masthead correction, yaw/heel rotation or iterative vessel-force equilibrium."],
            solver_name=self.name, solver_version=self.version,
        )
