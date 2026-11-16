# YJ64 Engineering Core — implementation status

This is the factual implementation ledger for `UNIFIED_ENGINEERING_DEVELOPMENT_PLAN.md`. A catalogue entry or design document is not an implemented solver.

## Status definitions

- **Implemented prototype** — executable code and automated tests exist; capability may be deliberately limited.
- **Partially implemented** — an executable foundation exists, but major parts of the intended capability remain.
- **Planned** — requirements are documented; no meaningful executable subsystem is present.
- **Not started** — no implementation identified.

## Consolidated work-package status

| Work package | Status | Existing implementation | Main remaining work |
|---|---|---|---|
| 1. Universal kernel, project model and extension contracts | Partially implemented | Request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass/CG/inertia, evidence/stale-result tracking; evidence-aware material/environment foundation; unit-aware Quantity and extensible UnitRegistry added in the current pass | Coordinate frames, geometry primitives, typed loads/boundary conditions, persistent project/artifact store, complete provenance/version compatibility and plugin capability contracts |
| 2. Shared physics, materials, environments and evidence feedback | Partially implemented | Material identity/property evidence and in-memory registry; dry-air ideal-gas density; atmospheric-pressure seawater EOS-80; several bounded marine/aero calculations | Persistent verified datasets, humid air, pressure-aware seawater, viscosity/conductivity, cryogenic/plasma and other specialist models, experiment intake, discrepancy analysis, research-data collector and reviewed adaptive model updates |
| 3. Solver ecosystem and coupled multiphysics | Planned | Limited CalculiX truss adapter; CAD adapters exist but are not general solver adapters | Isolated solver workers, adapter contracts, OpenMDAO/OpenModelica/OpenFOAM/MOOSE/CEA/FEM integrations, coupled analysis orchestration, benchmarks and license/version management |
| 4. Materials, manufacturing, reverse engineering and invention | Partially implemented | Hull material screening; material evidence records; visual-reference metadata and annotations; some CAD generation | Persistent process-aware material datasets, additive/CNC/joining/heat-treatment workflows, tolerances, inspection, scan reconstruction, repair/lifecycle, structured TRIZ/USIT/SIT and other invention workflows |
| 5. Electrical power, electronics, instrumentation and communications | Planned | Requirements only | DC/AC networks, 12/24/48 V comparison, load/energy balance, batteries/BMS, generation/charging, cables/protection/faults, controls, sensors, navigation, communications and fail-safe behaviour |
| 6. Integrated marine application | Partially implemented | Parametric hull geometry/CAD; preliminary catamaran hydrostatics; mass budget; sail polar/apparent wind; coefficient-based aero/hydrodynamics; hull-material screening; hydrostatic panel pressure loads with polygon integration; ROV pressure-housing screen; prescribed six-DOF vessel point kinematics | Complete hull/global structure, stability/trim/damage, seakeeping, foils/rig/propulsion/propellers, electrical/electronics, accommodation/tanks/plumbing, integrated budgets and design validation |
| 7. Robotics, mechanisms and autonomous vehicles | Planned | Vessel base-point six-DOF kinematics is reusable groundwork; architecture requirements documented | Link/joint and multibody models, actuators, contact/balance on moving decks, manipulators, winches/hoists, ROV/AUV/UAV performance and local safety controllers |
| 8. Cross-domain application packs and open ecosystem | Planned | Physics domain catalogue and spaceflight target scope documented | Full aviation/space/industrial solvers, cryogenics/plasma where applicable, application packs, public module registry, contributor tooling and ecosystem integrations |

## Existing executable foundations

- **Core:** shared request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass properties, evidence and stale-result tracking.
- **Physics kernel:** evidence-aware material records and in-memory registry; dry-air ideal-gas density; atmospheric-pressure seawater density using UNESCO 1983 EOS-80.
- **New in current first-package pass:** `Quantity`, `UnitDefinition`, `UnitRegistry` and `DEFAULT_UNIT_REGISTRY` in `physics/kernel/quantities.py`. Includes explicit SI dimension vectors, named-unit conversion, offset temperature conversion, finite-value checks and extensible registration. Automated tests have been added; CI outcome is not yet confirmed.
- **Marine/aero:** preliminary catamaran hydrostatics, mass budget, sail polar from supplied data, apparent wind, coefficient-based aero/hydrodynamics, hull material screening.
- **Structures/ROV:** axial member screening, limited CalculiX axial truss adapter, ROV cylindrical pressure-housing screen, hydrostatic panel pressure-load generation including polygon integration.
- **Motion:** six-DOF rigid-body point kinematics for a supplied/prescribed vessel state. This is not wave-response prediction, seakeeping, sensor fusion or robot stabilization.
- **Geometry/visualization:** parametric hull geometry, limited SVG/OpenSCAD/FreeCAD generation adapters, image metadata/hash intake and structured human annotations.

## Immediate implementation sequence — Package 1

1. **Delivered in code; CI pending:** unit-aware quantities and extensible named-unit registry.
2. Coordinate frames, transforms and explicit frame-compatibility checks.
3. Reusable geometry primitives and validation.
4. Typed loads, boundary conditions and operating/environmental states.
5. Versioned plugin/solver capability declarations and compatibility rules.
6. Connect the common types to existing solvers incrementally without breaking public operations.

## Evidence and release policy

Automated tests verify software behaviour. Reference benchmarks verify numerical implementation. Experimental comparisons support physical validation. Independent engineering review, qualification and certification are separate levels. No prototype or screening result is a design approval or safe operating limit.

A model update must retain old versions, exact provenance, test evidence and applicability limits. New experimental data never silently overwrites a released model.
