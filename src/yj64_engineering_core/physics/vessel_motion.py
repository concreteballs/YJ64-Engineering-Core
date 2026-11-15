"""Rigid-body six-degree-of-freedom vessel motion kinematics.

This solver transforms a body-fixed equipment/robot point into the earth frame
and computes its velocity and acceleration from a supplied vessel state.
It does not predict waves or vessel response.
"""
from __future__ import annotations

import math
from typing import Any

from ..models import AnalysisRequest, AnalysisResult


def _vec(value: Any, name: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    result = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"{name}[{index}] must be numeric")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{name}[{index}] must be finite")
        result.append(number)
    return tuple(result)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mat_vec(matrix, vector):
    return tuple(sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3))


def _rotation_matrix(roll: float, pitch: float, yaw: float):
    """Body-to-earth rotation Rz(yaw) * Ry(pitch) * Rx(roll)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


class VesselMotionKinematicsSolver:
    """Transform body-fixed point kinematics using a supplied 6-DOF vessel state."""

    name = "YJ64 six-DOF vessel motion kinematics"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "marine.vessel_motion_point_kinematics"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        parameters = request.parameters
        geometry = parameters.get("geometry") or {}
        conditions = parameters.get("operating_conditions") or {}
        point_body = _vec(geometry.get("point_body_m"), "geometry.point_body_m")
        position = _vec(conditions.get("vessel_position_xyz_m", [0.0, 0.0, 0.0]), "vessel_position_xyz_m")
        velocity = _vec(conditions.get("linear_velocity_xyz_m_s", [0.0, 0.0, 0.0]), "linear_velocity_xyz_m_s")
        acceleration = _vec(conditions.get("linear_acceleration_xyz_m_s2", [0.0, 0.0, 0.0]), "linear_acceleration_xyz_m_s2")
        angles = _vec(conditions.get("orientation_rpy_rad", [0.0, 0.0, 0.0]), "orientation_rpy_rad")
        omega_body = _vec(conditions.get("angular_velocity_body_xyz_rad_s", [0.0, 0.0, 0.0]), "angular_velocity_body_xyz_rad_s")
        alpha_body = _vec(conditions.get("angular_acceleration_body_xyz_rad_s2", [0.0, 0.0, 0.0]), "angular_acceleration_body_xyz_rad_s2")

        rotation = _rotation_matrix(*angles)
        arm_earth = _mat_vec(rotation, point_body)
        omega_earth = _mat_vec(rotation, omega_body)
        alpha_earth = _mat_vec(rotation, alpha_body)
        point_position = _add(position, arm_earth)
        point_velocity = _add(velocity, _cross(omega_earth, arm_earth))
        point_acceleration = _add(
            _add(acceleration, _cross(alpha_earth, arm_earth)),
            _cross(omega_earth, _cross(omega_earth, arm_earth)),
        )

        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="screening_only",
            values={
                "point_position_earth_xyz_m": list(point_position),
                "point_velocity_earth_xyz_m_s": list(point_velocity),
                "point_acceleration_earth_xyz_m_s2": list(point_acceleration),
                "point_arm_earth_xyz_m": list(arm_earth),
                "angular_velocity_earth_xyz_rad_s": list(omega_earth),
                "angular_acceleration_earth_xyz_rad_s2": list(alpha_earth),
                "rotation_body_to_earth_matrix": [list(row) for row in rotation],
            },
            units={
                "point_position_earth_xyz_m": "m",
                "point_velocity_earth_xyz_m_s": "m/s",
                "point_acceleration_earth_xyz_m_s2": "m/s^2",
                "point_arm_earth_xyz_m": "m",
                "angular_velocity_earth_xyz_rad_s": "rad/s",
                "angular_acceleration_earth_xyz_rad_s2": "rad/s^2",
                "rotation_body_to_earth_matrix": "dimensionless",
            },
            method="rigid_body_6dof_point_kinematics",
            assumptions=[
                "Body axes are x-forward, y-starboard, z-down? No: x-forward, y-starboard, z-up; right-handed earth axes use the same orientation.",
                "Orientation uses roll about x, pitch about y, yaw about z with R = Rz(yaw) Ry(pitch) Rx(roll).",
                "Linear velocity and acceleration are expressed in earth axes; angular velocity and acceleration are expressed in body axes.",
                "The vessel is treated as a rigid body and the queried point is fixed in its body frame.",
            ],
            warnings=[
                "This transforms a supplied motion state; it does not predict vessel response to waves, wind, loading or control inputs.",
                "For a robot on deck, the point coordinates must be expressed relative to the vessel reference origin, and any robot articulation requires a separate kinematic chain.",
            ],
            limitations=[
                "No hydrodynamic added mass, damping, restoring coefficients, wave spectrum, RAOs, slamming or seakeeping prediction.",
                "No flexible hull/deck deformation, sensor fusion, state estimation, time-series interpolation or uncertainty propagation.",
                "No contact, traction, balance or robot control model; this solver supplies base-motion kinematics only.",
            ],
            solver_name=self.name,
            solver_version=self.version,
        )
