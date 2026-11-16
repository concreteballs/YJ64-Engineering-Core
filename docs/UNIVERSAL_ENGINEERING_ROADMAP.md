# Universal Engineering Capability Roadmap

The authoritative programme is UNIFIED_ENGINEERING_DEVELOPMENT_PLAN.md. External software candidate evaluation and adapter policy are specified in EXTERNAL_ENGINEERING_ECOSYSTEM.md. This document is the compact architectural companion and must remain synchronized with IMPLEMENTATION_STATUS.md.

## Platform objective

YJ64 is one open, model-independent engineering platform for many project classes. A yacht, aircraft, robot, spacecraft or industrial machine is a project assembled from shared typed data and compatible discipline modules—not a separate incompatible application.

The platform covers requirements, architecture, geometry, physics, materials, manufacturing, verification, testing, operation, maintenance and feedback. New disciplines and external solvers must be addable through versioned contracts without redesigning the common kernel.

## Architectural rule

YJ64 owns the canonical project model, common engineering semantics, provenance and extension contracts. Mature specialist tools may be reused through replaceable adapters. Do not rewrite mature numerical engines by default or replace the YJ64 kernel with a third-party platform. External tools are optional and isolated; core remains usable without them.

## Shared kernel responsibilities

- versioned projects, components, assemblies and interfaces;
- physical quantities, units and conversions;
- coordinate frames and transformations;
- reusable geometry and validation;
- materials and traceable property evidence;
- environmental states;
- loads, boundary conditions and operating states;
- uncertainty, provenance, validation state and artifact history;
- solver/plugin contracts, compatibility, capability discovery and dependency tracking.

The kernel owns shared representations and orchestration, not every discipline's equations. Discipline packs define their models, assumptions, numerical methods and applicability limits.

## Eight coordinated work packages

1. Universal kernel, project model and extension contracts — quantities/units, frames, geometry, loads, project/component schemas, provenance, persistence, dependencies and plugin compatibility.
2. Shared physics, materials, environments and evidence feedback — traceable datasets, cross-domain physical foundations, experiment intake, reproducible comparisons, research-data collection and reviewed model updates.
3. External engineering ecosystem, adapters and coupled execution — candidate/licence/API evaluation, isolated workers, versioned adapters, workflow coupling, standards, benchmarks and replaceable solver integrations.
4. Materials, manufacturing, reverse engineering and invention — process-aware materials; metal casting and polymer/other-material moulding; material-specific forging and thermomechanical forming (including titanium); heat treatment and surface engineering; additive/CNC/joining; inspection, repair, reverse engineering and structured invention methods. Process routes link to source literature and evidence, not generic recipes.
5. Electrical power, electronics, instrumentation and communications — DC/AC energy systems, controls, sensors, navigation, RF/satellite/acoustic/optical/tether links and fail-safe behaviour.
6. Integrated marine application — complete cruising sailing catamaran structural, hydrodynamic, rig, propulsion, electrical, accommodation, plumbing, navigation and safety systems.
7. Robotics, mechanisms and autonomous vehicles — humanoid/non-humanoid robots, marine robots, ROV/AUV, UAV, mechanisms, actuators, winches, cranes and moving-platform operation.
8. Cross-domain application packs and open ecosystem — aviation, space, industrial machinery, energy systems, celestial mechanics, astrodynamics, cosmology and open module registry.
9. Human operational knowledge and emergency assistance — medical first aid, chemistry, field materials/minerals, geography, woodworking, survival, emergency signalling and repair.
10. Adaptive task assembly and offline deployment — compose several disciplines/tools for a concrete task; selectable local knowledge bundles and optional on-device LLM/solver runtime.

Related work inside a package should be delivered as coherent increments rather than isolated micro-projects.

## External engineering candidates

Initial candidates, subject to evaluation rather than automatic adoption:
- OpenMDAO — multidisciplinary orchestration and optimization;
- SALOME — geometry, meshing, pre/post-processing and solver supervision;
- FreeCAD — parametric CAD and geometry exchange;
- OpenModelica/OMSimulator, FMI and SSP — equation-based system simulation and co-simulation;
- OpenFOAM — CFD;
- MOOSE — multiphysics FEM;
- CalculiX, Elmer FEM and Code_Aster — structural/multiphysics FEM options;
- NASA Software Catalog tools — task-specific aerospace, mission and system models.

3DEXPERIENCE, Siemens Xcelerator/Simcenter and Ansys ModelCenter are commercial workflow benchmarks or optional integrations, not the open-source base.

No candidate is a mandatory dependency until its exact release, licence/dependencies, interfaces, maintenance, security, resource requirements and benchmark performance are reviewed. See EXTERNAL_ENGINEERING_ECOSYSTEM.md.

## Standards and interoperability

Evaluate FMI/SSP for system-model exchange and co-simulation, STEP for suitable solid CAD exchange, and each solver's supported mesh/field formats. Versioned YJ64 contracts remain canonical. Every adapter documents preserved, transformed, approximated and discarded information. A standard interface does not itself validate a model or define the complete coupling algorithm.

## Physical discipline catalogue

The target catalogue is maintained in PHYSICS_DOMAIN_CATALOG.md. It includes mechanics and structural analysis; fluids, hydrodynamics and aerodynamics; thermodynamics and heat transfer; electrical engineering and electromagnetics; acoustics and vibration; optics; materials science, chemistry and electrochemistry; controls and robotics; reliability and optimization; cryogenics; high-temperature/compressible gas dynamics; plasma where applicable; radiation and space environments; and future disciplines.

Manufacturing-process and technical-literature architecture is specified in MANUFACTURING_PROCESS_AND_TECHNICAL_KNOWLEDGE.md. Planned scope is not evidence that process simulations or production recipes exist.

The catalogue is target scope, not evidence that a solver is implemented. Every discipline declares models, assumptions, operating envelope, uncertainty, dependencies and validation evidence.

## Experimental evidence and model updates

Every experiment or error report is tied to exact model/solver version, inputs, environment, measurement method, calibration, uncertainty and output. A research-data collector preserves source and licence metadata. There is no universal fixed percentage for significant corrections: decisions consider experimental uncertainty, repeatability, model uncertainty, sensitivity, applicability range and consequence. New evidence can trigger more data, a bounded extension, an alternative model or a reviewed update. It never silently changes a released model.

## Civilian trajectory scope

Support general trajectory mechanics and legitimate civilian applications, including rescue line-throwing, signalling and safety-oriented net capture. Assess actual function, design, payload, energy source, foreseeable use and risks. Do not develop or optimize automatic/rifle/cannon weapon barrels, ammunition, weapon launch systems or terminal/penetrating effects. The term "ballistics" alone does not prohibit general physics or civilian rescue engineering.

## Evidence levels

Keep software correctness, numerical verification, experimental validation and engineering qualification distinct. Results state exact revisions, solver/model version, assumptions, applicability limits, uncertainty, warnings and evidence level. A successful software test is not physical validation or product certification.

## Current implementation baseline

Executable prototypes already exist for core contracts/dispatch/pipeline/component dependencies, mass properties, evidence-aware materials, dry-air and atmospheric-pressure seawater density, bounded marine/aero solvers, axial member screening, a limited CalculiX adapter, ROV pressure-housing screening, hydrostatic panel pressure loads with polygon integration, prescribed six-DOF vessel point kinematics, limited hull geometry/CAD adapters, visual-reference metadata intake and unit-aware quantities.

See IMPLEMENTATION_STATUS.md for exact status and remaining work. Do not count a planned catalogue entry or an external candidate as implemented.


## Cross-cutting position, time and navigation services

A shared source-aware service seeks all permitted GNSS/GPS, network, external-device, sensor and manual position/time sources; retains the last trusted fix; estimates dead-reckoned motion with growing uncertainty; detects stale or implausible data; and maintains UTC separately from timezone. Routine marine navigation integrates existing charting/anchoring products through supported interfaces and formats rather than rebuilding them. Emergency Celestial Navigation remains a separate optional offline operational module. See POSITION_TIME_AND_NAVIGATION_INTEGRATION.md.

## Celestial mechanics and scientific hypothesis testing

Astronomy, astrometry, ephemerides, orbital and gravitational dynamics, trajectory mechanics and cosmological model testing form a reusable discipline pack. Formal proofs, symbolic calculations, numerical predictions and observational comparisons remain distinct evidence types. See CELESTIAL_MECHANICS_AND_COSMOLOGY.md.

## Field assistance and adaptive task assembly

Medical, chemistry, materials/minerals, geography, woodworking, shelter, water, energy and communications knowledge are optional operational modules. Adaptive Task Assembly composes them with engineering solvers and available resources for a specific task. Offline bundles and optional local models support operation without internet while exposing data freshness and safety limits. See FIELD_SURVIVAL_AND_EMERGENCY_ASSISTANCE.md and ADAPTIVE_TASK_ASSEMBLY_AND_OFFLINE_DEPLOYMENT.md.
