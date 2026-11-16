# YJ64 Engineering Platform — Final Unified Development Plan

**Authoritative programme:** this document governs development of concreteballs/YJ64-Engineering-Core on main. Other repositories and branches are outside this plan unless separately authorized.

**Companion documents**
- UNIVERSAL_ENGINEERING_ROADMAP.md — concise architecture and domain roadmap.
- EXTERNAL_ENGINEERING_ECOSYSTEM.md — candidate inventory, evaluation policy, adapter requirements and integration gates.
- IMPLEMENTATION_STATUS.md — factual implementation ledger; code and tests, not plans, determine status.

## 1. Mission

Build an open, model-independent, interdisciplinary engineering platform with one extensible project model and physical kernel. A yacht, aircraft, robot, spacecraft or industrial machine must be represented as a different engineering project on the same platform—not as a separate incompatible application.

YJ64 supports the full lifecycle: requirements and concepts; system architecture and interfaces; geometry and physical modelling; analysis, simulation and optimization; materials and manufacturing; verification and physical testing; operation, maintenance, repair and evidence feedback.

The cruising yacht is the first large integrated demonstration project, not the platform's specialization limit.

## 2. Strategic architecture decision

**YJ64 owns the common engineering language and canonical project truth; specialist engines may be reused.**

The platform will not attempt to rewrite every CAD system, mesh generator, FEM package, CFD solver, system simulator or optimizer. Mature external tools will be evaluated and, where justified, connected through versioned adapters and isolated workers.

YJ64 remains independent:
- one canonical, versioned project/component/assembly/interface model;
- shared physical quantities, units, coordinate frames, geometry references, materials, environments, loads and operating states;
- solver-neutral contracts, explicit conversions and compatibility checks;
- provenance, assumptions, uncertainty, evidence levels, dependencies and stale-result tracking;
- replaceable discipline packs and solver adapters;
- public extension rules so independent developers can add capabilities without modifying the core.

No external tool owns or silently changes canonical YJ64 project state. Native tool files may be retained as source artifacts, with explicit import/export mappings and recorded fidelity limitations.

## 2A. Cross-cutting capability — multilingual engineering workspace

Internationalization, technical-document translation and localized unit presentation are platform-wide capabilities, not yacht-specific features. Their requirements and staged design are defined in MULTILINGUAL_ENGINEERING_WORKSPACE.md. The project model must preserve language-independent engineering data and source documents while allowing user-selected interface/document languages and display-unit profiles. Translation must never silently alter numeric values, symbols, equations, identifiers, standard references or engineering meaning. Unit conversion is dimension-checked and independent from language translation.

## 3. Delivery principles

1. Build common foundations once.
2. Keep specialist physics modular; each discipline owns its equations, numerical methods, assumptions, applicability bounds and validation.
3. Reuse mature tools before rewriting them.
4. Avoid single-vendor dependency; provide replaceable implementations or document why this is impractical.
5. Keep external engines optional; core YJ64 remains usable without them.
6. Trace every result to exact input revisions, solver/model version, configuration, assumptions, warnings, uncertainty, provenance and evidence.
7. Unknown means unknown; never invent material properties, loads, process parameters, tolerances, uncertainty or safety margins.
8. Separate software correctness, numerical verification, experimental validation and product qualification.
9. Design the open extension ecosystem around stable contracts, compatibility tests and reviewable manifests.
10. Apply safety boundaries according to actual application context, not isolated scientific vocabulary.

## 4. Existing executable foundations — do not rebuild

These capabilities already have code and must not be recreated as new work. Extend, connect or validate them:
- core request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass/centre-of-gravity/inertia, evidence and stale-result tracking;
- evidence-aware material records and an in-memory material registry;
- dry-air ideal-gas density within declared limits and atmospheric-pressure seawater density using UNESCO 1983 EOS-80;
- preliminary catamaran hydrostatics, mass budget, supplied-data sail polar, apparent wind, coefficient-based aerodynamic/hydrodynamic calculations and hull-material screening;
- axial-member screening and a limited CalculiX truss adapter;
- ROV cylindrical pressure-housing screening;
- hydrostatic panel pressure-load generation, including polygon integration;
- six-degree-of-freedom rigid-body vessel point kinematics for a supplied/prescribed state;
- parametric hull geometry and limited SVG/OpenSCAD/FreeCAD generation adapters;
- visual-reference intake with image metadata/hash and structured human annotations;
- unit-aware Quantity, UnitDefinition, UnitRegistry and default unit registry.

These are bounded prototypes, not complete disciplines. Their limitations remain explicit in IMPLEMENTATION_STATUS.md and solver documentation. A catalogue entry is not evidence of implementation.

## 5. Eight coordinated work packages

Related subtasks should be designed, implemented and tested together as coherent increments rather than scattered micro-projects.

### Package 1 — Universal kernel, project model and extension contracts

Build together:
- unit-aware physical quantities, dimension checking and extensible unit registry, with locale-independent canonical values, SI/metric/US/marine display profiles and per-field overrides;\n- document-import unit policy: preserve source, apply selected profile or ask; profile defaults never override explicit field-level engineering conventions;\n- voice-command intent interface for explicit, dimension-checked unit changes, with ambiguity resolution and user confirmation before persistent changes;\n- distinction between nominal standards designations (such as NPS/DN pipe sizes) and actual physical dimensions;\n- localization foundations: language-neutral identifiers and schemas, interface/document locale metadata, terminology/glossary contracts, and safe technical-document translation workflows;
- coordinate frames, handedness conventions, transforms and frame-compatibility validation;
- reusable geometry primitives, stable references and geometric validation;
- typed loads, boundary conditions, operating states and environmental references;
- versioned project/component/assembly/interface schemas;
- persistent project/artifact/provenance model, dependency graph, revision pinning and stale-result handling;
- solver/plugin manifests, capability declarations, compatibility/version rules, structured diagnostics and permissions.

The kernel owns common representations and conventions, not every discipline's equations. Plugins declare input/output schemas, units, coordinate conventions, assumptions, applicability bounds, dependencies, version, licence and evidence level. External execution is isolated and resource-bounded. Arbitrary LLM-generated code is never executed inside the core process.

**Completion gate:** a test plugin consumes common typed quantities and project data, returns a traceable result, rejects incompatible units/frames/schema versions, and causes dependent outputs to become stale after upstream changes.

### Package 2 — Shared physics, materials, environments and evidence feedback

Build together:
- persistent, versioned material datasets with batch/product form, condition, heat treatment, orientation, temperature, source, test method and uncertainty;
- environment models: pressure-aware seawater, humid air, viscosity, conductivity, thermal properties, atmospheric/ocean profiles, gases, cryogenic fluids, vacuum and other justified media;
- reusable physical foundations and cross-discipline state exchange;
- public issue/experiment intake linked to exact solver versions, inputs, outputs, test conditions and measurement methods;
- prediction-versus-measurement discrepancy analysis and reproducible regression cases;
- research-data collector for openly accessible publications and experimental datasets, preserving source, licence, extraction method and uncertainty.

**Adaptive model-update policy:** no universal fixed percentage threshold. Significance depends on measurement uncertainty, repeatability, model uncertainty, downstream sensitivity, applicability range and consequence of error. Outcomes may be no change, request more evidence, add a bounded applicability region or propose an alternative model. Model changes require review, benchmark/regression tests and versioned release. New data never silently rewrites a trusted model.

The owner's proposed spectral-database method remains a design input; specify its data model and algorithm before implementation.

**Completion gate:** an experiment can be reproduced and compared against a pinned model; a proposed correction can be reviewed without overwriting a released model.

### Package 3 — External engineering ecosystem, adapters and coupled execution

This is a first-class architectural workstream, not an afterthought.

Build together:
- candidate inventory and versioned technical/licence evaluation records;
- adapter SDK/contracts and capability discovery;
- isolated, resource-bounded workers with timeout, cancellation, least privilege and structured logs;
- solver installation/availability metadata, exact version pinning and licence/dependency tracking;
- explicit unit, frame, mesh, field, schema and sign-convention conversion/validation;
- workflow composition, coupled analyses, synchronization and convergence criteria;
- benchmark suite, cross-solver comparisons and reproducibility records;
- adapter lifecycle, compatibility matrix, deprecation and replacement policy.

**Priority candidates by role—not pre-approved dependencies:**
- orchestration and optimization: OpenMDAO;
- geometry, meshing, pre/post-processing and solver supervision: SALOME;
- parametric CAD and geometry exchange: FreeCAD;
- equation-based system modelling and co-simulation: OpenModelica/OMSimulator, FMI and SSP;
- CFD: OpenFOAM;
- multiphysics FEM: MOOSE;
- structural FEM comparisons: existing CalculiX adapter, Elmer FEM and Code_Aster;
- task-specific NASA tools: NASA Software Catalog, including GMAT, Trick, GUNNS and NASA CEA where documented scope matches a real task.

Commercial 3DEXPERIENCE, Siemens Xcelerator/Simcenter and Ansys ModelCenter are workflow/architecture benchmarks and optional integrations where access and terms permit—not the open-source base.

**Integration rule:** OpenMDAO is not treated as a physics solver; SALOME is not treated as a universal solver; FMI is an interface standard, not a solver or complete coupling algorithm. Each candidate is evaluated according to its actual role.

**Evaluation gates:**
A. exact release, maintenance, platform and licence/dependency screening;
B. standalone documented example with captured inputs, settings, logs, outputs and resource use;
C. one narrow adapter operation with validated conversions and failure handling;
D. benchmark against analytical, published or independently checked references;
E. integration into a YJ64 project with provenance, revision pinning, stale propagation, cancellation and error containment;
F. explicit adopt/pilot/defer/reject decision.

No external engine becomes mandatory merely because it is popular. Core reduced mode must remain usable without optional tools. Licence review covers exact release, bundled dependencies, plugins, bindings, datasets and intended distribution; a process boundary is not assumed to eliminate legal obligations.

**First pilots:** OpenMDAO with two simple YJ64 components; SALOME with one geometry/mesh round trip; FreeCAD STEP round trip; OpenModelica/FMI with a small coupled physical system; OpenFOAM with one bounded CFD benchmark; and a like-for-like structural comparison between CalculiX and one of Elmer/Code_Aster/MOOSE.

**Completion gate:** at least one optional external solver is connected through a documented adapter, passes a reproducible benchmark, returns traceable data and fails safely when unavailable or incompatible. Candidate review records and compatibility tests exist for the first selected tools.

Detailed policy: EXTERNAL_ENGINEERING_ECOSYSTEM.md.

### Package 4 — Materials, manufacturing, reverse engineering and invention

Build together:
- metals, polymers, elastomers, ceramics, glass, composites, sandwich, foam, adhesives and coatings;
- process-aware properties and manufacturing routes;
- polymer/composite and metal additive manufacturing, CNC machining, joining/welding and heat-treatment models;
- tolerances, fits, GD&T, inspection and non-destructive testing;
- CAD/CAM exchange and machine-specific postprocessor boundaries;
- reverse engineering from measurements, scans, images and samples with uncertainty;
- repair, obsolete-part replacement, lifecycle and maintenance workflows;
- structured invention methods: TRIZ, USIT, SIT/ASIT, functional and contradiction analysis, morphology, biomimicry, analogies, QFD, FMEA/FMECA, HAZOP and design-for-X.

Methods generate hypotheses, not proof. Machine-specific NC/G-code and qualified process parameters require exact machine, controller, tooling, setup, process and validated postprocessor. Safety-critical parts require appropriate engineering review, material/process qualification, inspection and testing.

### Package 5 — Electrical power, electronics, instrumentation and communications

Build together because these share power, interfaces, environment, controls and fault management:
- complete DC/AC electrical architecture; compare 12/24/48 V rather than preselecting;
- batteries/BMS, solar, MPPT, alternators, generators, shore power, inverters and converters;
- loads, energy/autonomy, cable sizing, voltage drop/heating, protection, short-circuit/fault analysis, grounding, bonding, isolation and corrosion;
- motors, drives, power electronics, sensors, embedded controllers and control-system simulation;
- navigation, radar, AIS, GNSS, sonar, displays, alarms, health monitoring and vessel/vehicle automation;
- RF/satellite, acoustic/optical communication, tethered links, relays, link budgets, cybersecurity and loss-link behaviour;
- EMC, environmental qualification, redundancy and fail-safe operation.

The smartphone is a user interface or supplementary sensor/compute node, never the sole safety controller for a vessel or autonomous vehicle. Local deterministic controllers retain critical safety functions.

### Package 6 — First integrated application: complete marine systems

Use the shared platform to design a complete cruising sailing catamaran:
- hulls, decks, bulkheads, crossbeams, global/local structure and stability;
- hydrostatics, seakeeping, hydrodynamics, foils, rudders and appendages;
- mast, sails, rigging, folding/stowage and automated sail handling;
- diesel/electric/hybrid propulsion, propellers, cooling and exhaust;
- electrical/energy architecture and marine electronics;
- accommodation, galley, refrigeration, tanks, plumbing, watermaker and utilities;
- anchoring, mooring, deck equipment, safety and service access;
- mass/CG, volume, power, thermal, cost, maintenance and operational budgets.

All subsystems share one project state. Changes trigger relevant cross-checks. Distinguish preliminary screening from full structural analysis, seakeeping validation, class review and physical qualification.

### Package 7 — Robotics, mechanisms and autonomous vehicles

Build a common framework for humanoid/non-humanoid robots, deckhands, inspection robots, ROV/AUV, UAV, rescue/cargo systems and industrial automation.

Include chassis/link/joint models, DOF, multibody dynamics, electric/geared, cable/tendon, hydraulic, pneumatic and compliant actuators, transmissions, grippers, winches, cranes, propellers/rotors, balance/contact, mass/CG/inertia, power/thermal budgets and fault states. Marine variants account for moving decks, six-DOF vessel motion, salt, ingress, cold, shock, vibration, corrosion, tethering, stowage and recovery. UAVs need local return/divert/land logic; underwater vehicles need physically appropriate acoustic, optical or tether communications.

### Package 8 — Cross-domain application packs and open ecosystem

Add reusable packs for:
- aviation, seaplanes and amphibious aircraft;
- space launch vehicles, spacecraft, orbital systems and ground-support equipment;
- industrial machinery, process systems and energy infrastructure;
- road/rail vehicles and other future domains.

Space and advanced propulsion scope includes astrodynamics, flight dynamics, compressible/high-temperature gas dynamics, propulsion, cryogenics, plasma where physically applicable, thermal protection, vacuum/outgassing, radiation, structures, avionics/GNC, power, life support, test infrastructure and mission assurance. Plasma is a specialist model, not an assumption that every nozzle flow is fully ionized.

Also deliver public module registry, contributor documentation, compatibility tests, reference datasets, visualization/simulation presentation and optional website/publishing/commercial integrations. External repositories may consume YJ64 interfaces but are not modified by this plan.

## 6. Civilian trajectory and launch-device scope

Support general trajectory mechanics and legitimate civilian engineering, including rescue line-throwing, signalling devices, sport/industrial launch mechanisms and safety-oriented net capture concepts for hazardous or unauthorized drones. Evaluate actual function, energy source, payload, environment, bystander risks and legal operating context.

Do not design or optimize automatic/rifle/cannon weapon barrels, ammunition, weapon launch systems or terminal/penetrating effects. The word "ballistics" alone does not prohibit general physics or civilian rescue engineering. Classification depends on actual design and intended/foreseeable use, not pressure level or payload material alone.

## 7. Common quality and validation gates

Every result records exact inputs/revisions, solver/model version, configuration, assumptions, applicability range, uncertainty, warnings, provenance and validation evidence.

Evidence levels:
1. concept or incomplete inputs;
2. analytical screening;
3. numerical simulation;
4. independently reviewed analysis;
5. prototype manufactured;
6. bench tested;
7. field tested;
8. qualified/certified for a specifically stated use.

Software tests verify implementation behaviour. Reference benchmarks verify numerical behaviour. Experiments support physical validation. Independent engineering review, qualification and certification address the complete application. No one level implies the next.

## 8. Delivery and governance

- Work only in this repository and main unless separately authorized.
- Deliver one coherent package increment per pass; combine related subtasks.
- Preserve functioning prototypes and tests; refactor only for a documented reason.
- Update implementation status, design documentation and tests with each capability.
- Run relevant tests and CI; report exact results and never claim unverified success.
- Preserve backwards compatibility where practical; document breaking changes and migration paths.
- Keep external adapters and discipline packs independently versioned and replaceable.
- Record decisions affecting canonical schemas, public APIs, licences or security boundaries.
- Treat the external candidate list as a living evaluation queue, not a promise to integrate every named tool.

## 9. Immediate execution order

1. Finish Package 1: coordinate frames/transforms, geometry primitives/validation, typed loads and boundary conditions; connect types to existing solvers.
2. Start Package 3 candidate inventory and licence/API review in parallel with kernel work, without adding premature runtime dependencies.
3. Build first thin integration pilots only after relevant YJ64 contracts are stable.
4. Continue Package 2 evidence/material/environment foundations, then application packages according to dependencies.

**Approval baseline:** this document and its companion roadmap define the approved target architecture. Implementation status remains separate and factual; approval does not imply planned capabilities are already built.
