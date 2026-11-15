# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system. The current practical workflow is parametric yacht geometry plus independently routed engineering solvers.

## Current capabilities

- Versioned JSON engineering requests and responses using SI units.
- Explicit dispatcher and pipeline for CAD and physics backends.
- Parametric monohull envelope with SVG plan/profile/sections, editable OpenSCAD source, FreeCAD macro and optional STL rendering.
- Controlled geometry edits from structured instructions, with before/after records.
- PNG/JPEG reference intake, hashes, normalized markup and structured observations from a vision-capable model.
- Axial structural screening and a narrow CalculiX T3D2 verification case.
- Coefficient-based aerodynamic and hydrodynamic force screening.
- Sail aerodynamic polar interpolation with finite-span induced-drag correction.
- Sail fabric mass screening with separate warp/weft stiffness, strength and creep inputs.
- Apparent-wind vector calculation from true wind and vessel velocity.
- Twin-hull displacement and reserve-buoyancy screening from station-based hull geometry.
- Vessel mass ledger for structure, rig, propulsion, systems, interior, stores and tank loads, including first-moment centre of gravity.

## Sail aerodynamic model

`SailAerodynamicsSolver` is available as `physics.aerodynamics.sail_polar`. It interpolates a supplied table of angle of attack, lift coefficient (CL), profile drag coefficient (CD) and quarter-chord moment coefficient (CM). It rejects requests outside the supplied polar range, adds a classical induced-drag correction from sail aspect ratio and Oswald efficiency, and returns lift, profile drag, induced drag, total drag, pitching moment, Reynolds number and vessel-axis force components.

Run:

    python examples/sail_polar_screen.py

The included polar is illustrative test data only, not a validated sail characteristic. Replace it with data representative of the actual sail shape, trim, rig and Reynolds-number range before using results for design decisions. This solver is steady-flow screening, not CFD; it does not generate sail polars or model aeroelasticity, rig interference, gusts or automatic trim. See docs/FLOW_ANALYSIS.md.

## Yacht hull geometry

The first hull is a single-hull outer envelope defined by ordered longitudinal stations: x position, half-beam, keel height, chine height and deck-edge height. The section is a simple five-point chine profile. It is an editable geometry demonstrator, not a complete naval-architecture model.

The current hull has no internal frames, stringers, bulkheads, laminate schedule, thickness or scantlings. It has no hydrostatics, stability, resistance, slamming or hull-specific shell FEM. The existing CalculiX T3D2 adapter is only a single axial truss check and must not be treated as a hull-strength calculation.

## Catamaran displacement and mass budget

`CatamaranHydrostaticsSolver` is available as `physics.hydrostatics.catamaran_displacement`. It integrates the submerged cross-sectional area of exactly two station-based hull envelopes at a user-supplied design waterline and maximum geometric waterline. It reports displaced volume/mass and geometric reserve volume. This is a preliminary displacement estimate only: it does not calculate trim, heel, stability curves, downflooding, regulatory freeboard, damaged stability or a safe load line. The maximum waterline is an explicit design input, not a certified limit.

`VesselMassBudgetSolver` is available as `physics.vessel.mass_budget`. Its item ledger can classify masses as structure, rig_sails, propulsion, systems, interior, stores or other. Tank loads are calculated from capacity, fill fraction and fluid density, with tank/fittings tare added separately. The result includes category totals and a point-mass centre of gravity. Tank free-surface effects and stability are not yet calculated.

The mass budget must be populated by subsystem: hulls/crossbeams/foils; mast, boom, sails and standing/running rigging; anchors, chain and windlass; engines/electric drives/shafts/propellers; batteries, fuel and charging systems; steering/rudders; accommodation, furniture and appliances; plumbing and tanks; provisions, refrigeration, safety gear and payload. Avoid double counting. Propulsion architecture (shaft-line, saildrive, pod, etc.) must be represented as its actual equipment and installation mass, not selected by the mass ledger.

## Foiling catamaran engineering roadmap

1. Validate and import sail and foil polars with source and Reynolds-number metadata.
2. Calculate apparent wind from true wind and vessel velocity; solve sail trim and force/moment equilibrium.
3. Add hull resistance and hydrostatics.
4. Add foil lift/drag, cavitation and ventilation models.
5. Couple sail, hull and foil loads in a six-degree-of-freedom transient displacement-to-foil transition model.
6. Transfer loads into hull shell, crossbeams, mast and foil attachments.
7. Optimise for cruising accommodation, payload, range, stability, structural margins and operating envelope.

The displacement-to-foil transition must be treated as a transient problem, not inferred from a single steady-state lift calculation.

## Data exchange and reliability

STEP for solid CAD exchange; DXF/SVG for drawings; STL for meshes; versioned JSON for parameters, edits, observations and results. Every calculation identifies its method, inputs, assumptions, units, warnings and limitations. External CAD/solver processes must run with bounded time/resources in isolated workers. Safety-critical designs require independent engineering review and physical validation.

## Development

Python 3.11 or newer.

    python -m pip install -e .
    python -m unittest discover -s tests -v
