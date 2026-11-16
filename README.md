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
- Canonical revisioned component records shared by CAD, physics, material and manufacturing modules, with mass properties, interfaces, pinned dependencies, evidence and deterministic fingerprints.

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

## Hull material comparison

`HullMaterialScreeningSolver` is available as `physics.hull.material_screen`. It compares explicit build-ups for marine aluminium, glass-fibre composite, carbon-fibre composite, sandwich/honeycomb panels and reinforced concrete. Wood is excluded.

Each layer is entered using cured laminate areal mass or supplied thickness and density. Secondary installation mass, material/manufacturing cost per square metre, annual maintenance cost and major-maintenance interval are optional explicit inputs. No generic material weight, price or maintenance rate is invented. The solver returns layer and total build-up mass plus any cost/maintenance values supplied.

This is not a structural equivalence comparison: equal surface area does not mean equal strength, stiffness, fatigue life, impact resistance or safety. Each alternative must be independently sized for the same loads. Aluminium requires weld, corrosion and galvanic-isolation review; composites require laminate/core/adhesive, impact and repair review; concrete requires reinforcement, cracking, shrinkage, creep and corrosion assessment. The current solver does not calculate scantlings, laminate theory, structural margins or lifecycle cost forecasts.

## Universal engineering roadmap

The long-term capability plan for general engineering, materials, metal additive manufacturing, CNC machining, heat treatment, repair of unavailable components, solver integration and TRIZ-based invention support is maintained in [docs/UNIVERSAL_ENGINEERING_ROADMAP.md](docs/UNIVERSAL_ENGINEERING_ROADMAP.md). This is a roadmap and interface target; it does not imply that these capabilities are already implemented.

## Chemistry and artificial muscle architecture

The coordinated but independently versioned Chemistry & Molecular Design and Artificial Muscle Engineering discipline packs are specified in [docs/CHEMISTRY_AND_ARTIFICIAL_MUSCLE_MODULE_ARCHITECTURE.md](docs/CHEMISTRY_AND_ARTIFICIAL_MUSCLE_MODULE_ARCHITECTURE.md). This is target architecture, not a claim that the packs or their scientific solvers are implemented.

## Canonical engineering component model

The shared component data contract is documented in [docs/COMPONENT_MODEL.md](docs/COMPONENT_MODEL.md). It gives each part or subsystem a stable ID and revision, stores geometry/material/mass properties and interfaces, pins dependencies to exact revisions, and fingerprints the serialized inputs. `stale_component_dependencies()` detects direct dependencies whose referenced revision changed or disappeared. Transitive invalidation and artifact regeneration remain responsibilities of the future project-graph manager; this data model does not certify component safety or manufacturability.

Calculation traceability: every dispatched CAD/physics response now includes `provenance.input_digest_sha256`, calculated from the exact canonical request plus selected operation. `ComponentCalculationRecord` can pin a result to exact component revisions, and `stale_calculations()` flags results when a referenced component changes or disappears. `EngineeringProjectGraph` now maintains an in-memory component registry, validates dependency revisions and rejects cycles. It propagates stale status transitively through component dependencies and marks calculations stale when their inputs are affected. This is not yet persistent project storage or automatic solver/artifact reruns.

## Shared economic and local sourcing

The reusable `economics` pack compares buying a complete part with sourcing a bill of materials and assembling locally. It ranks caller-supplied supplier offers by estimated total landed cost for a declared destination and optional local radius, including supplier distance, pickup/delivery mode, explicit taxes, supplier-grouped shipping and declared assembly costs. A read-only Mouser Search API adapter normalizes catalog prices, price breaks, availability, minimum quantities and lead times into supplier offers. The user selects only the destination on the map or explicitly grants GPS access. The engineering agent authors material/part categories, search terms, quantities, technical constraints, budget, delivery deadline and local/domestic/international/China market scopes. An authenticated `POST /api/discovery` endpoint validates the agent's request and returns a search plan. A read-only 1688 catalogue adapter is implemented through the optional paid Nexscope API (10–19 credits per call, guarded by an explicit credit budget); no paid calls have been made. Live multi-provider execution, durable queueing, shipping quotes, customs, FX conversion and purchasing are not yet connected. See [docs/AGENT_SOURCING_API.md](docs/AGENT_SOURCING_API.md).


**Destination selection:** the root page (`/`) lets the user choose only the delivery point on a map or explicitly request GPS. It exports destination coordinates for the engineering agent. Procurement parameters are generated by the agent through the authenticated discovery API.

