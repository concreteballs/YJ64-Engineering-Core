# YJ64 flow analysis

## Sail polar solver

`SailAerodynamicsSolver` is registered for `physics.aerodynamics.sail_polar`. It interpolates a caller-supplied table of angle of attack, lift coefficient (CL), profile drag coefficient (CD), and pitching-moment coefficient (CM). Alpha rows must be strictly increasing; the solver rejects requests outside the polar range rather than extrapolating.

Geometry inputs: `sail_area_m2`, `span_m`, `mean_chord_m`, `polar_points` (rows with `alpha_deg`, `cl`, `cd`, `cm`) and optional `polar_source` provenance label.

Operating inputs: `apparent_wind_speed_m_s`, `air_density_kg_m3`, `dynamic_viscosity_pa_s`, `angle_of_attack_deg`, `apparent_wind_from_angle_deg` (from the bow, positive starboard), and `oswald_efficiency` (0 < e <= 1).

Finite-span induced drag uses `CDi = CL^2 / (pi * e * AR)` with `AR = span^2 / sail_area`. The result includes lift, profile drag, induced drag, total drag, quarter-chord pitching moment, Reynolds number and force components in vessel axes (X forward, Y starboard). Positive CM means nose-up. Lift components use the explicit vessel-axis vector transform documented in the solver.

Run `python examples/sail_polar_screen.py`. The example polar is illustrative only and is not validated design data. Use a polar representative of the actual sail/rig configuration and Reynolds-number range before engineering decisions.

## Sail fabric and construction

`SailMaterialSolver` is registered for `physics.sail.material_screen`. Supply `geometry.sail_area_m2` and either `material.areal_density_kg_m2` (preferred, mass per fabric area) or both `bulk_density_kg_m3` and `thickness_m`. Optional `seam_and_overlap_fraction`, `reinforcement_mass_kg` and `hardware_mass_kg` add construction allowances to the mass estimate.

Record the actual sail cloth/laminate's `warp_tensile_stiffness_n_m`, `weft_tensile_stiffness_n_m`, `in_plane_shear_stiffness_n_m`, directional tensile strengths and `long_term_creep_strain_fraction` where supplier data exists. Warp and weft are kept separate: the membrane is orthotropic, and its orientation relative to the sail panels matters. Sail type, panel layout, cloth choice, cut, seams, reinforcements and load paths must be selected as one design rather than treating fabric as a generic sheet. The current model estimates mass and retains mechanical properties; it does not predict the flying shape or certify strength.

## Apparent wind

`ApparentWindSolver` is registered for `physics.aerodynamics.apparent_wind`. Inputs are true wind speed and wind-from angle plus vessel velocity components in the same reference frame. It subtracts vessel velocity from true-air velocity and returns apparent-wind speed, components and wind-from angle. X is forward, Y is starboard; positive angles are to starboard.

## Model limits

This is a steady, low-order screening solver. It does not generate a polar from sail geometry, calculate flexible sail shape, aeroelastic deformation, mast/rig interference, wind gradient, gust response, dynamic stall, sail interaction, or automatic trim. It does not solve apparent-wind equilibrium with vessel velocity. It is not CFD and cannot establish that a vessel can foil.

## Wider flow-analysis roadmap

1. Import validated sail and foil polars with source, Reynolds-number and configuration metadata.
2. Calculate apparent wind from true wind and vessel velocity; couple material-specific sail stiffness and cut with sail trim and force/moment equilibrium.
3. Add hull resistance, hydrostatics and free-surface effects.
4. Add foil lift/drag, cavitation and ventilation screening with validated models.
5. Couple aerodynamic and hydrodynamic loads in a six-degree-of-freedom transient displacement-to-foil transition model.
6. Transfer loads into hull shell, crossbeams, mast and foil-attachment structural models.
7. Optimise for cruising accommodation, payload, range, stability, structural margins and operating envelope.

Each fidelity level must retain its own provenance, validation evidence and limitations. A low-order estimate must never be presented as CFD.
