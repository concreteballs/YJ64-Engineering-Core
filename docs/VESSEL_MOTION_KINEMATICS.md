# Vessel motion point kinematics

Operation: `marine.vessel_motion_point_kinematics`

Solver: `VesselMotionKinematicsSolver` (version 0.1.0).

## Purpose

Transforms the position, velocity and acceleration of a point fixed to a rigid vessel (for example, a deck-mounted robot base, sensor or winch) from vessel/body coordinates into earth coordinates using a supplied six-degree-of-freedom motion state.

This is a kinematics utility, not a seakeeping or wave-response predictor.

## Input

`geometry.point_body_m` is the point position relative to the vessel reference origin in metres.

Optional `operating_conditions` fields (all default to zero):

- `vessel_position_xyz_m`: vessel reference-origin position in earth axes.
- `orientation_rpy_rad`: roll, pitch and yaw in radians.
- `linear_velocity_xyz_m_s`: translational velocity in earth axes.
- `linear_acceleration_xyz_m_s2`: translational acceleration in earth axes.
- `angular_velocity_body_xyz_rad_s`: angular velocity in body axes.
- `angular_acceleration_body_xyz_rad_s2`: angular acceleration in body axes.

Coordinate convention: x forward, y starboard, z up; right-handed axes. Orientation matrix is (R=R_z(\psi)R_y(\theta)R_x(\phi)), mapping body vectors to earth axes.

## Equations

For body-fixed point vector (r_b), rotation (R), translational velocity (v), angular velocity (\omega) and angular acceleration (\alpha):

- (r_e=Rr_b)
- (p_e=p_{origin}+r_e)
- (v_{point}=v+\omega_e\times r_e)
- (a_{point}=a+\alpha_e\times r_e+\omega_e\times(\omega_e\times r_e))

Angular velocity and acceleration are rotated from body to earth axes before use.

## Output

Earth-frame point position, velocity and acceleration; rotated arm vector; earth-frame angular velocity/acceleration; and body-to-earth rotation matrix. Shared result status is `screening_only`.

## Limits

- Motion is prescribed by the caller. No wave spectrum, RAO, hydrodynamic coefficients, added mass, damping, restoring, wind loading or seakeeping prediction.
- Rigid body only; no hull/deck flexibility.
- No robot joint chain, contact/traction, balance controller, state estimation, time interpolation or uncertainty propagation.
- A robot's articulated motion must be composed with this base transform by a separate mechanism solver.
- Confirm axis conventions and sensor mounting transforms before using measured IMU data.
