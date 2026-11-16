# YJ64 Engineering Platform — Unified Development Plan

**Authoritative plan:** this document defines the consolidated implementation strategy for `concreteballs/YJ64-Engineering-Core`, branch `main`. Other repositories and branches are outside this work unless the owner explicitly authorizes them.

## Mission

Build an open, model-independent, interdisciplinary engineering platform with one extensible project and physical kernel. A yacht, aircraft, robot, spacecraft or industrial machine must be represented as a different engineering project on the same platform—not as a separate incompatible application.

YJ64 must not need to predict every future engineering discipline. New disciplines, solver engines, datasets and application domains must be addable through versioned contracts without redesigning the kernel.

The platform is intended to support the engineering lifecycle: requirements and concepts; architecture and interfaces; geometry and physical modelling; analysis and optimization; materials and manufacturing; verification and physical testing; operation, maintenance, repair and feedback.

The yacht is the first large integrated demonstration project, not the platform's specialization limit.

## Delivery principles

1. **Build shared foundations once.** Common quantities, units, coordinate frames, geometry, materials, environments, loads, provenance and project state belong in the shared kernel.
2. **Keep specialist physics modular.** Each discipline owns its equations, assumptions, numerical methods, applicability limits and validation evidence.
3. **Integrate rather than rewrite.** Reuse mature external solvers through adapters when licensing, interfaces, security and technical suitability permit.
4. **Preserve traceability.** Every input, model, result, artifact and test refers to exact versions and sources. Upstream changes mark dependent outputs stale.
5. **Unknown means unknown.** Never invent material properties, loads, process parameters, uncertainty or safety margins.
6. **Separate software correctness from engineering validity.** Passing unit tests does not validate a physical model; a validated model does not certify a complete product.
7. **Open extension ecosystem.** Independent developers can publish discipline packs and adapters against stable, documented contracts.
8. **Safety by application context.** Evaluate intended function, design and foreseeable use; do not apply blanket restrictions to an entire scientific discipline.

## What is already implemented

The following are existing executable foundations and must not be re-created as new work. They may be extended, refactored or validated further.

- Core request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass/centre-of-gravity/inertia records, evidence and stale-result tracking.
- Evidence-aware material identity/property records and an in-memory material registry.
- Dry-air ideal-gas density within declared limits and atmospheric-pressure seawater density using UNESCO 1983 EOS-80.
- Preliminary catamaran hydrostatics, mass budget, sail polar using supplied data, apparent wind, coefficient-based aerodynamic/hydrodynamic calculations and hull-material screening.
- Axial-member screening and a limited CalculiX truss adapter.
- ROV cylindrical pressure-housing screening.
- Hydrostatic panel pressure-load generation, including polygon integration mode.
- Six-degree-of-freedom rigid-body vessel point kinematics for a supplied/prescribed motion state.
- Parametric hull geometry and limited SVG/OpenSCAD/FreeCAD generation adapters.
- Visual reference intake that records image metadata/hash and structured human annotations.

These are prototypes or bounded capabilities, not complete disciplines. Exact limitations are recorded in `IMPLEMENTATION_STATUS.md` and the relevant solver documentation.

## Consolidated implementation programme

The programme is deliberately grouped into **eight substantial work packages**. Each package combines related work that should be designed, implemented and tested together. Subtasks are not independent mini-projects; deliver a coherent increment per implementation pass.

### Package 1 — Universal kernel, project model and extension contracts

**First package to execute.**

Build together:
- unit-aware physical quantities and extensible unit registry;
- coordinate frames and transformations;
- reusable geometry primitives and validation;
- typed loads, boundary conditions, operating states and environmental references;
- versioned project/component/assembly and interface schemas;
- persistent project/artifact/provenance model, dependency tracking and stale-result handling;
- stable solver/plugin contracts, capability declarations, compatibility/version rules and structured diagnostics.

The kernel owns shared representation and conventions—not every discipline's equations. A plugin must declare input/output schemas, units, coordinate conventions, assumptions, applicability bounds, dependencies, version, license and evidence level. External execution must be isolated and resource-bounded. Do not execute arbitrary LLM-generated code inside the core process.

**Completion gate:** a test plugin can consume common typed quantities and project data, return a traceable result, reject incompatible units/frames/schema versions and cause dependent results to be marked stale when upstream data changes.

### Package 2 — Shared physics, materials, environments and evidence feedback

Build together:
- expand the current material registry into persistent, versioned, traceable datasets, preserving batch/product form, condition, heat treatment, orientation, temperature, source, test method and uncertainty;
- expand environment models: pressure-aware seawater, humid air, viscosity, conductivity, thermal properties, atmospheric/ocean profiles, gases, cryogenic fluids, vacuum and other supported media;
- implement reusable physical foundations and cross-discipline state exchange;
- establish a public issue/experiment intake workflow linked to exact solver versions, inputs, outputs and test conditions;
- compare submitted measurements with predictions, classify discrepancies and create reproducible regression cases;
- create a research-data collector for openly accessible publications and experimental datasets, retaining source, license, extraction method and uncertainty.

**Adaptive model-update policy:** do not use one fixed percentage threshold. Significance must depend on measurement uncertainty, repeatability, model uncertainty, sensitivity of downstream outputs, operating range and consequence of error. The system may recommend no change, collect more evidence, add a bounded applicability region or propose a new model. Model changes require review, benchmark/regression tests and versioned release; collected data must never silently rewrite a trusted model. The owner's proposed spectral-database method is a design input to be specified before implementing its algorithm.

**Completion gate:** a submitted experiment can be reproduced, compared and traced; a proposed model correction can be evaluated without overwriting the released model.

### Package 3 — Solver ecosystem and coupled multiphysics execution

Build together:
- common adapters and isolated workers for suitable mature tools;
- solver discovery, installation/availability metadata, license compatibility and version pinning;
- unit/frame/schema conversion and validation at adapter boundaries;
- orchestration of coupled analyses with explicit data dependencies and convergence criteria;
- reference benchmarks and cross-solver comparisons.

Candidate tools to evaluate—not blindly depend on—include OpenMDAO, OpenModelica, OpenFOAM, MOOSE, NASA CEA, Elmer FEM, CalculiX, Code_Aster and FreeCAD. Select per task based on capabilities, license, maintainability, interfaces and reproducibility. The core must remain usable when an optional external engine is unavailable.

**Completion gate:** at least one external solver is connected through a documented adapter and produces a reproducible, traceable result; failure or incompatible output is contained and reported.

### Package 4 — Materials, manufacturing, reverse engineering and invention

Build together:
- metal, polymer, elastomer, ceramic, glass, composite, sandwich, foam, adhesive and coating data;
- process-aware properties and manufacturing routes;
- polymer/composite and metal additive manufacturing, CNC machining, joining, welding and heat-treatment process models;
- tolerances, fits, GD&T, inspection and non-destructive testing;
- CAD/CAM exchange and machine-specific postprocessor boundaries;
- reverse engineering from measurements, scans, images and samples with uncertainty;
- repair, obsolete-part replacement and lifecycle/maintenance workflows;
- structured invention-method library: TRIZ, USIT, SIT/ASIT, functional analysis, contradiction analysis, morphology, biomimicry, analogies, QFD, FMEA/FMECA, HAZOP and design-for-X.

Methods generate candidate hypotheses, not proof. Machine-specific NC/G-code and qualified manufacturing parameters require exact machine, controller, tooling, setup, process and validated postprocessor. Safety-critical parts require suitable engineering review, material/process qualification, inspection and tests.

### Package 5 — Electrical power, electronics, instrumentation and communications

Build together because these systems share power, interfaces, environment, controls and fault management:
- complete DC/AC electrical architecture; compare 12/24/48 V rather than preselecting;
- batteries/BMS, solar, MPPT, alternators, generators, shore power, inverters and converters;
- loads, energy/autonomy, cable sizing, voltage drop/heating, protection, short-circuit/fault analysis, grounding, bonding, isolation and corrosion;
- motors, drives, power electronics, sensors, embedded controllers and control-system simulation;
- navigation, radar, AIS, GNSS, sonar, displays, alarms, health monitoring and vessel/vehicle automation;
- RF/satellite, acoustic and optical communication, tethered links, relays, link budgets, cybersecurity and loss-link behaviour;
- EMC, environmental qualification, redundancy and fail-safe operation.

The smartphone may be a user interface or supplementary sensor/compute node, never the sole safety controller for a vessel or autonomous vehicle. Local deterministic controllers retain critical safety functions.

### Package 6 — First integrated application: complete marine systems

Use the shared platform to design the complete cruising sailing catamaran, including:
- hulls, decks, bulkheads, crossbeams, global/local structural loads and stability;
- hydrostatics, seakeeping, hydrodynamics, foils, rudders and appendages;
- mast, sails, rigging, folding/stowage and automated sail handling;
- diesel/electric/hybrid propulsion, propellers, cooling and exhaust;
- complete electrical/energy architecture and marine electronics;
- accommodation, galley, refrigeration, tanks, plumbing, watermaker and utilities;
- anchoring, mooring, deck equipment, safety and service access;
- mass/CG, volume, power, thermal, cost, maintenance and operational budgets.

All subsystems must share one project state. A change in one subsystem must trigger relevant checks elsewhere. The project must distinguish preliminary screening from full structural analysis, seakeeping validation, class review and physical qualification.

### Package 7 — Robotics, mechanisms and autonomous vehicles

Build a common mechanism and vehicle framework supporting humanoid and non-humanoid robots, deckhands, inspection robots, ROV/AUV, UAV, rescue/cargo systems and industrial automation.

Include chassis/link/joint models, DOF, multibody dynamics, actuators (electric, geared, cable/tendon, hydraulic, pneumatic and compliant systems), transmissions, grippers, winches, cranes, propellers/rotors, balance/contact, mass/CG/inertia, power/thermal budgets and fault states. Marine variants must account for moving decks, six-DOF vessel motion, salt, ingress, cold, shock, vibration, corrosion, tethering, stowage and recovery. UAVs need local return/divert/land logic; underwater vehicles need physically appropriate acoustic, optical or tether communications.

### Package 8 — Cross-domain application packs and open ecosystem

Add and maintain reusable application packs for:
- aviation, seaplanes and amphibious aircraft;
- space launch vehicles, spacecraft, orbital systems and ground-support equipment;
- industrial machinery, process systems and energy infrastructure;
- road/rail vehicles and other future domains.

Space and advanced propulsion scope includes astrodynamics, flight dynamics, compressible/high-temperature gas dynamics, propulsion-system modelling, cryogenics, plasma where physically applicable, thermal protection, vacuum/outgassing, radiation, structures, avionics/GNC, power, life support, test infrastructure and mission assurance. Plasma is a specialist model, not an assumption that every nozzle flow is fully ionized.

Also deliver the public module registry, contributor documentation, compatibility tests, reference datasets, visualization/simulation presentation and optional website/publishing/commercial integrations. External repositories may consume YJ64 interfaces, but are not modified by this plan.

## Civilian trajectory and launch-device scope

Provide general trajectory mechanics and legitimate civilian engineering, including rescue line-throwing systems, signalling devices, sports/industrial launch mechanisms and safety-oriented net capture concepts for hazardous or unauthorized drones. Evaluate the actual function, energy source, projectile/payload, environment, risks to bystanders and legal operating context.

This does not include designing or optimizing automatic/rifle/cannon weapon barrels, ammunition, weapon launch systems or terminal/penetrating effects. The word "ballistics" alone is not a reason to block general physics or civilian rescue calculations. A device is assessed by its actual design and intended/foreseeable use; pressure level or payload material alone is not a sufficient classification rule.

## Common quality and validation gates

Every module/result must distinguish:
- concept or incomplete inputs;
- analytical screening;
- numerical simulation;
- independently reviewed analysis;
- prototype manufactured;
- bench tested;
- field tested;
- qualified/certified for a specifically stated use.

Every result records exact inputs and revisions, solver/model version, assumptions, applicability range, uncertainty, warnings, provenance and validation evidence. Software tests verify implementation behaviour; benchmark cases verify numerical behaviour; experiments inform physical validity; independent engineering review and qualification address the complete application.

## Delivery method

- Work only in this repository and `main` unless separately authorized.
- Execute one coherent package increment per pass; combine related subtasks rather than creating disconnected micro-commits.
- Keep completed prototypes and tests; do not rewrite functioning code without a reason.
- Update `IMPLEMENTATION_STATUS.md`, the relevant design docs and tests with every delivered capability.
- Run the relevant test suite and CI; report exact outcomes without claiming unverified success.
- Preserve backwards compatibility where practical; document breaking changes and migration paths.
- Keep optional solver adapters and discipline packs independently versioned and replaceable.

## Immediate first implementation pass

Start Package 1 with **unit-aware physical quantities and an extensible unit registry**, then proceed to coordinate frames, geometry primitives, and common load/boundary-condition schemas. This sequence creates shared typed foundations for existing and future solvers without duplicating current material/environment models.
