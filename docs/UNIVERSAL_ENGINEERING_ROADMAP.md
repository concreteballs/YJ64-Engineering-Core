# Universal Engineering Capability Roadmap

The authoritative implementation programme is `UNIFIED_ENGINEERING_DEVELOPMENT_PLAN.md`. This document is its compact architectural companion; it must remain synchronized with that plan and `IMPLEMENTATION_STATUS.md`.

## Platform objective

YJ64 is one open, model-independent engineering platform for many project classes. A yacht, aircraft, robot, spacecraft or industrial machine is a project assembled from shared typed data and compatible discipline modules—not a separate incompatible application.

The platform covers requirements, architecture, geometry, physics, materials, manufacturing, verification, testing, operation, maintenance and feedback. New disciplines and external solvers must be addable through versioned contracts without redesigning the common kernel.

## Shared kernel responsibilities

The common kernel owns:
- versioned projects, components, assemblies and interfaces;
- physical quantities, units and conversions;
- coordinate frames and transformations;
- reusable geometry and validation;
- materials and traceable property evidence;
- environmental states;
- loads, boundary conditions and operating states;
- uncertainty, provenance, validation state and artifact history;
- solver/plugin contracts, compatibility and dependency tracking.

The kernel owns common representations and orchestration, not every discipline's equations. Discipline packs define their models, assumptions, numerical methods and applicability limits. External solvers run in isolated, resource-bounded workers.

## Consolidated delivery packages

Implement these as eight coordinated work packages, not as isolated mini-projects:

1. **Universal kernel, project model and extension contracts** — quantities/units, frames, geometry, loads, project/component schemas, provenance, persistence, dependencies and plugin compatibility.
2. **Shared physics, materials, environments and evidence feedback** — traceable material/environment datasets, cross-domain physical foundations, experiment/bug intake, reproducible comparisons, open research-data collection and reviewed adaptive model updates.
3. **Solver ecosystem and coupled multiphysics execution** — adapters, isolated workers, external-tool version/license management, coupled analyses and benchmarks.
4. **Materials, manufacturing, reverse engineering and invention** — process-aware materials, additive/CNC/joining/heat-treatment, inspection, repair, reverse engineering and structured invention methods.
5. **Electrical power, electronics, instrumentation and communications** — complete DC/AC energy systems, controls, sensors, navigation, networks, RF/satellite/acoustic/optical/tether links and fail-safe behaviour.
6. **First integrated application: complete marine systems** — the cruising sailing catamaran and its complete structural, hydrodynamic, rig, propulsion, electrical, accommodation, plumbing, navigation and safety systems.
7. **Robotics, mechanisms and autonomous vehicles** — humanoid/non-humanoid robots, marine robots, ROV/AUV, UAV, mechanisms, actuators, winches, cranes and moving-platform operation.
8. **Cross-domain application packs and open ecosystem** — aviation, space, industrial machinery, energy systems, module registry, contributor tooling, visualization and optional publishing/commercial integrations.

Detailed requirements and completion gates are maintained in the unified development plan. The package order reflects dependencies; related subtasks within a package should be delivered together where practical.

## Physical discipline catalogue

The target catalogue is maintained in `PHYSICS_DOMAIN_CATALOG.md`. It includes mechanics and structural analysis; fluids, hydrodynamics and aerodynamics; thermodynamics and heat transfer; electrical engineering and electromagnetics; acoustics and vibration; optics; materials science, chemistry and electrochemistry; controls and robotics; reliability and optimization; cryogenics; high-temperature/compressible gas dynamics; plasma physics where applicable; radiation and space environments; and other future disciplines.

The catalogue is a target scope, not evidence that a solver is implemented. Every discipline must declare its model, assumptions, operating envelope, uncertainty, dependencies and validation evidence.

## External solver strategy

Evaluate and integrate suitable tools rather than rewriting mature numerical engines by default. Candidate tools include OpenMDAO, OpenModelica, OpenFOAM, MOOSE, NASA CEA, Elmer FEM, CalculiX, Code_Aster and FreeCAD. Selection is per capability and must consider license compatibility, interfaces, reproducibility, security, maintenance and validation. Optional external engines must not become mandatory for the core to function.

## Experimental evidence and model updates

Every experiment or error report must be tied to the exact model/solver version, inputs, environment, measurement method, calibration, uncertainty and output. A research-data collector may ingest openly accessible publications and datasets while preserving provenance and license metadata.

There is no universal fixed percentage for a significant correction. The update decision must account for experimental uncertainty, repeatability, model uncertainty, sensitivity, applicability range and consequence of error. New evidence can trigger more data collection, a bounded extension, an alternative model or a reviewed update. No collected data silently changes a released model. The owner's proposed spectral-database method remains to be specified before its algorithm is implemented.

## Civilian trajectory scope

General trajectory mechanics and legitimate civilian applications are supported, including rescue line-throwing, signalling and safety-oriented net capture. The actual function, design, payload, energy source, foreseeable use and risks are assessed. YJ64 does not develop or optimize automatic/rifle/cannon weapon barrels, ammunition, weapon launch systems or terminal/penetrating effects. The term "ballistics" alone does not prohibit general physics or civilian rescue engineering.

## Evidence levels

Keep software correctness, numerical verification, experimental validation and engineering qualification distinct. Results must state exact revisions, solver/model version, assumptions, applicability limits, uncertainty, warnings and evidence level. A successful software test is not a physical validation or product certification.

## Current implementation baseline

Executable prototypes already exist for core contracts/dispatch/pipeline/component dependencies, mass properties, evidence-aware materials, dry-air and atmospheric-pressure seawater density, several preliminary marine/aero solvers, axial member screening, a limited CalculiX adapter, ROV pressure-housing screening, hydrostatic panel pressure loads with polygon integration, prescribed six-DOF vessel point kinematics, limited hull geometry/CAD adapters and visual-reference metadata intake.

See `IMPLEMENTATION_STATUS.md` for exact status and remaining work. Do not count a planned catalogue entry as implemented.
