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

## 5. Nine coordinated work packages

Related subtasks should be designed, implemented and tested together as coherent increments rather than scattered micro-projects.

### Package 1 — Universal kernel, project model and extension contracts

### Implemented foundations — extend and integrate; do not rebuild
- Unit-aware quantities, dimension checking and extensible unit registry; canonical SI values; SI/metric/European metric/US customary/UK imperial/marine-hybrid display profiles; per-field overrides; document unit-policy values; explicit voice-conversion intent parsing; nominal NPS/DN designations kept distinct from physical dimensions.
- Single-root coordinate-frame tree, handedness validation and rigid transforms.
- Frame-aware geometry primitives with finite-value, degeneracy and frame-consistency checks.
- Typed force/moment loads and boundary conditions for fixed, displacement, rotation, pressure and temperature cases.
- Existing request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass properties, evidence and stale-result tracking.
- UTF-8 Markdown/plain-text source intake with immutable source bytes, SHA-256 identity, language metadata and stable source spans.

These foundations have automated tests. They are not complete end-user workflows: speech recognition/UI, mesh-bound load mapping, full project persistence and broader document formats remain open.

### Remaining Package 1 work
- Localization foundations: language-neutral identifiers and schemas, interface/document locale metadata, terminology/glossary contracts, and safe technical-document translation workflows.
- Versioned persistent project/component/assembly/interface schemas and a durable project/artifact/provenance store.
- Revision-pinned calculations and artifacts, dependency tracking, stale-result propagation across persisted project state and reproducible reload.
- Solver/plugin manifests, capability declarations, input/output schema compatibility, unit/frame requirements, applicability bounds, licence/dependency declarations and structured diagnostics.
- Connect shared coordinate frames, geometry, typed loads and boundary conditions to existing solver interfaces through explicit, validated adapters; reject unsupported mappings rather than silently dropping data.
- Document ingestion beyond UTF-8 Markdown/plain text (PDF/DOCX/OCR), translation providers, glossary enforcement, protected-token integrity checks, review and translated export.
- Actual speech recognition, ambiguity prompts and confirmation UI for voice-driven unit changes.

The kernel owns common representations and conventions, not every discipline's equations. Plugins declare their capabilities and compatibility explicitly. External execution is isolated and resource-bounded. Arbitrary LLM-generated code is never executed inside the core process.

**Completion gate:** a test plugin consumes persisted project data and shared typed inputs, returns a traceable result, rejects incompatible units/frames/schema versions, and causes dependent outputs to become stale after upstream changes; the project can be reloaded without losing provenance.

### Package 2 — Shared physics, materials, environments and evidence feedback

Build together:
- persistent, versioned material and process datasets distinguishing alloy/grade, chemical composition, batch, product form, casting/forging/rolling/extrusion/additive route, heat treatment, thermomechanical history, grain/texture orientation, defects, surface condition, temperature, test method, source, uncertainty and applicability;
- process-specific property evolution: properties depend on composition, product form, manufacturing route, deformation/solidification history, heat treatment, direction, temperature and service condition, not on grade name alone;
- environment models: pressure-aware seawater, humid air, viscosity, conductivity, thermal properties, atmospheric/ocean profiles, gases, cryogenic fluids, vacuum and other justified media;
- reusable physical foundations and cross-discipline state exchange;
- public issue/experiment intake linked to exact solver versions, inputs, outputs, test conditions and measurement methods;
- prediction-versus-measurement discrepancy analysis and reproducible regression cases;
- research-data collector for openly accessible publications and experimental datasets, preserving source, licence, extraction method and uncertainty.

**Adaptive model-update policy:** no universal fixed percentage threshold. Significance depends on measurement uncertainty, repeatability, model uncertainty, downstream sensitivity, applicability range and consequence of error. Outcomes may be no change, request more evidence, add a bounded applicability region or propose an alternative model. Model changes require review, benchmark/regression tests and versioned release. New data never silently rewrites a trusted model.

The owner's proposed spectral-database method remains a design input; specify its data model and algorithm before implementation.

Material/process reference datasets distinguish handbook values, supplier datasheets, standards, measured batch data and model-derived estimates. Process knowledge links to source passages and experimental evidence; it is not silently promoted into a solver or universal recipe.

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
- metals and alloys (ferrous and non-ferrous, including aluminium, copper, nickel, titanium and specialist alloys), polymers (thermoplastics and thermosets), elastomers, ceramics, glass, composites, sandwich structures, foams, adhesives and coatings;
- process-aware material models linking composition and grade to product form, manufacturing history, microstructure, defects, heat treatment, surface state, directionality, temperature and measured properties;
- **Casting of metals and other castable materials:** sand, investment, permanent-mould, die, centrifugal and other relevant metal casting routes; polymer injection, compression, transfer and other moulding routes; mould/core design, filling and flow, cooling/solidification/curing, shrinkage, feeding, porosity, inclusions, warpage, residual stress, process windows and inspection. Each material family gets its own constitutive, thermal and process models;
- **Forging and thermomechanical forming:** open-die/free forging, closed-die/impression-die forging, upsetting, drawing-out, ring rolling and other routes; hot/warm/cold forming where applicable; material-specific temperature windows, strain/strain-rate history, deformation path, friction, die contact, reheating, cooling, anisotropy, grain flow/recrystallization, loads, flash, allowances and defects. Steel, aluminium, copper, nickel and titanium alloys require distinct validated process data and models;
- **Material-specific forging methods:** do not assume that a sequence or workpiece geometry suitable for one material is suitable for another. Steel, titanium alloys, bulat/welded-patterned steels and other alloys may require substantially different deformation strategies because of their distinct deformation mechanisms, phase behaviour, temperature/strain-rate sensitivity and microstructural evolution. The user's forge-example observations (including square-section steel forging and a demonstration of a titanium workpiece progressively reduced from several sides before flattening) are illustrative prompts to investigate, not proposed industrial recipes or validated universal rules. Record such observations as attributed examples, then verify them against authoritative literature and alloy-specific evidence;
- **Heat treatment and surface engineering:** annealing, normalizing where applicable, quenching, tempering, solution treatment, ageing/precipitation hardening, stress relief, carburizing, nitriding, induction/flame treatment and other alloy-specific processes; time-temperature cycles, atmosphere, phase transformations, precipitation, hardness, distortion, residual stress, oxidation and case depth;
- polymer/composite and metal additive manufacturing, CNC machining, joining/welding and hybrid manufacturing, with process-aware models and validated machine/process boundaries;
- tolerances, fits, GD&T, inspection, non-destructive testing, dimensional metrology and process quality records;
- CAD/CAM exchange and machine-specific postprocessor boundaries;
- reverse engineering from measurements, scans, images and samples with uncertainty;
- repair, obsolete-part replacement, lifecycle and maintenance workflows;
- structured invention methods: TRIZ, USIT, SIT/ASIT, functional and contradiction analysis, morphology, biomimicry, analogies, QFD, FMEA/FMECA, HAZOP and design-for-X.

Methods generate hypotheses, not proof. Machine-specific NC/G-code and qualified process parameters require exact machine, controller, tooling, setup, process and validated postprocessor. Safety-critical parts require appropriate engineering review, material/process qualification, inspection and testing.

**Completion gate:** material records trace composition, product form, manufacturing route and condition; each process model declares its material family, process window, assumptions and validation evidence; incompatible material/process combinations are rejected. Detailed scope: MANUFACTURING_PROCESS_AND_TECHNICAL_KNOWLEDGE.md.

### Package 5 — Electrical power, electronics, instrumentation and communications

Build together because these share power, interfaces, environment, controls and fault management:
- complete DC/AC electrical architecture; compare 12/24/48 V rather than preselecting;
- batteries/BMS, solar, MPPT, alternators, generators, shore power, inverters and converters;
- loads, energy/autonomy, cable sizing, voltage drop/heating, protection, short-circuit/fault analysis, grounding, bonding, isolation and corrosion;
- motors, drives, power electronics, sensors, embedded controllers and control-system simulation;
- navigation, radar, AIS, multi-constellation GNSS, sonar, displays, alarms, health monitoring and vessel/vehicle automation;
- a shared Position & Time Awareness service: source-ranked location/time acquisition, last trusted fix, uncertainty-aware sensor fusion and dead reckoning, peer-device time comparison, UTC/time-zone separation, spoofing/jamming and stale-source detection;
- Navigation Integration Hub for licensed/official integrations with established chartplotters, marine-navigation, anchoring and alarm applications; prioritize supported APIs, NMEA 0183/2000, Signal K, GPX and other documented exchange formats rather than recreating mature charting products;
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
- optional Emergency Celestial Navigation module, separately invokable from routine navigation, for offline observation planning, improvised angle-measuring tools, calibration, time/position fixes, uncertainty-aware lines of position and manual fallback procedures;
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
- road/rail vehicles and other future domains;
- celestial mechanics, astrometry, ephemerides, solar-system dynamics, orbital mechanics, trajectory design, gravitational modelling and cosmological model testing, with explicit separation between established reference models and user-supplied hypotheses.

Space and advanced propulsion scope includes astrodynamics, flight dynamics, compressible/high-temperature gas dynamics, propulsion, cryogenics, plasma where physically applicable, thermal protection, vacuum/outgassing, radiation, structures, avionics/GNC, power, life support, test infrastructure and mission assurance. Plasma is a specialist model, not an assumption that every nozzle flow is fully ionized.

Also deliver public module registry, contributor documentation, compatibility tests, reference datasets, visualization/simulation presentation and optional website/publishing/commercial integrations. External repositories may consume YJ64 interfaces but are not modified by this plan.


### Package 9 — Human operational knowledge, emergency assistance and adaptive field problem-solving

Build optional, independently installable operational modules on top of shared kernel and discipline packs. They are not part of the structural/physical solver core and must remain usable as separate application workflows:
- first aid and emergency medical guidance: scene safety, triage support, symptom/injury information, basic first-aid procedures, escalation and emergency-service contact guidance; clearly distinguish observations, possible explanations and diagnosis; conservative, source-reviewed content, local emergency-number packs and explicit limits;
- practical chemistry and environmental safety: combustion principles, safe fire-starting options, water-treatment selection, contamination limits, material compatibility, chemical identification confidence, hazardous-reaction warnings and safe storage; never imply that boiling removes chemical contaminants;
- field materials, minerals, geography, ecology, woodworking, shelter, energy, food/water and repair knowledge, with local-region packs and source/evidence traceability;
- emergency communications and signalling: prioritize internationally recognized visual, acoustic and approved radio distress methods; assess available equipment and legal constraints before proposing radio construction or transmission;
- situation-driven construction and repair: use an inventory of available tools/materials, measured properties and environmental constraints to generate several feasible options, compare risks/resources, and produce stepwise instructions;
- offline knowledge bundles and optional on-device language models, with versioned sources, checksums, update provenance and graceful operation without network access.

Medical and chemical content is advisory and safety-bounded. The system must prioritize immediate danger reduction and professional/emergency help where available, avoid unsupported diagnosis or hazardous recipes, identify uncertainty, and never present generated procedures as certified instructions. Adaptive assembly may compose approved knowledge, tools and deterministic calculations; it must not execute arbitrary generated code or silently authorize dangerous actions.

**Completion gate:** a field task can be represented with available resources, location/environment, constraints and objective; the system produces traceable alternatives with assumptions, hazard checks, confidence and offline source references. Emergency medical/chemical content passes dedicated expert review before operational release.

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

1. Package 1: connect the implemented shared frames, geometry, loads and boundary-condition types to existing solver interfaces; build durable project/artifact/provenance persistence and plugin capability contracts.
2. Package 3: review exact releases, licences/dependencies, APIs and workflows for selected external tools without adding premature runtime dependencies.
3. Build thin integration pilots only after relevant YJ64 contracts are stable.
4. Expand Package 2 evidence/material/environment foundations, then application packages according to dependencies.

**Approval baseline:** this document and its companion roadmap define the approved target architecture. Implementation status remains separate and factual; approval does not imply planned capabilities are already built.


## 10. Cross-cutting capability — mathematical notation and symbolic workspace

LaTeX-based mathematical notation, equation rendering, semantic expression contracts, dimensional validation and replaceable symbolic/numerical backends are platform-wide capabilities. Their architecture, candidate technologies, safety boundaries and acceptance criteria are defined in MATHEMATICAL_NOTATION_AND_SYMBOLIC_WORKSPACE.md.

LaTeX is the primary human-readable notation, not the calculation engine. Rendering, parsing, semantic representation and computation remain separate layers. MathJax is the initial rendering candidate; SymPy is the initial symbolic-backend candidate subject to release/licence/API review and a bounded benchmark. The existing Quantity/unit system must participate in dimensional validation. No symbolic result is accepted as physically validated solely because it was rendered or computed.


### Mathematical formalization and proof-assistant ecosystem

The mathematical workspace includes a multi-prover formal verification layer. Lean 4 + Mathlib is the first pilot candidate, while the architecture permits independent adapters for Rocq/Coq, Isabelle/HOL, Agda, Metamath, HOL Light, HOL4, PVS and ACL2. SAT/SMT engines such as Z3 and cvc5 are a separate optional category. The common contract preserves each prover's logic, assumptions, axioms, libraries, native proof artifacts and trusted checker; it must never imply that a formal proof validates physical assumptions or real-world performance. See MATHEMATICAL_NOTATION_AND_SYMBOLIC_WORKSPACE.md.


## 11. Cross-cutting capability — position, time and navigation interoperability

The platform provides a shared, source-aware Position & Time Awareness service used by marine, field, robotics and scientific modules. It seeks all permitted available location/time sources, records source identity, observation time, uncertainty, freshness and trust status, and preserves the last trusted fix. It supports multi-constellation GNSS, external receivers, compatible device/network positioning, permitted Wi-Fi/cellular/Bluetooth sources, connected instruments, manual fixes and celestial observations. Access is permission-gated and privacy-aware; network-derived positions are not treated as equivalent to a surveyed or GNSS fix.

When satellite positioning is unavailable, the service may estimate motion from calibrated phone/external sensors, compass, barometer, speed log, vessel data and environmental estimates. This is dead reckoning/sensor fusion, not a substitute for an absolute fix: uncertainty must grow with time and distance, source bias must be modelled, and weather/current data are contextual inputs rather than direct position measurements. Reacquired fixes correct the estimated track while preserving the original track and correction history. Spoofing, jamming, stale data and implausible jumps must be flagged.

Time is maintained internally against UTC with a monotonic clock and an uncertainty estimate. GNSS, network time, trusted external instruments and peer devices may contribute according to freshness and provenance. A peer's recent internet synchronization is evidence only when its synchronization time, source, clock drift and integrity can be assessed. Keep timezone/locale offsets separate from absolute time; detect manual clock changes; do not blindly copy a peer clock or change the operating-system clock. Preserve time-source history and apply explicit corrections to observations and calculations.

Routine marine navigation is integrated with established third-party charting, route-planning, anchoring and alarm products through documented/licensed APIs and exchange standards. YJ64 does not recreate proprietary chart databases or bypass access controls. Emergency Celestial Navigation is a separate optional module with offline procedures and explicit uncertainty.

Detailed requirements: POSITION_TIME_AND_NAVIGATION_INTEGRATION.md.

## 12. Cross-cutting capability — celestial mechanics and cosmological hypothesis testing

Provide a reusable discipline pack for astronomy, astrometry, celestial mechanics, orbital/trajectory mechanics, gravitational dynamics and cosmology. Support independent analytical, numerical and formal verification paths where suitable; preserve observational datasets, reference frames, time scales, constants, ephemeris versions, model assumptions and uncertainty. User hypotheses are first-class, versioned model candidates and must be compared against established reference models and observations without being silently promoted to accepted physics.

Connect mathematical expressions, multi-prover proof obligations, CAS/numerical calculations and physical models through shared typed variables and provenance. A formal proof establishes only its encoded assumptions and theorem; a numerical match is not experimental validation. Detailed scope: CELESTIAL_MECHANICS_AND_COSMOLOGY.md and MATHEMATICAL_NOTATION_AND_SYMBOLIC_WORKSPACE.md.

## 13. Cross-cutting capability — adaptive task assembly and offline deployment

A task may span several discipline packs and operational modules. Adaptive Task Assembly resolves the objective, available resources, environment, constraints, required knowledge and risk class; selects compatible modules/tools; builds a reviewable workflow; and returns alternatives, assumptions, missing inputs, hazards and evidence. Modules remain separately versioned and replaceable. Local deployment supports selectable signed/offline knowledge bundles, cached reference datasets and optional local LLM/solver components. Offline packages must disclose age and coverage of data and cannot claim live weather, chart corrections, medical updates or current conditions without a verified source.

Detailed requirements: ADAPTIVE_TASK_ASSEMBLY_AND_OFFLINE_DEPLOYMENT.md and FIELD_SURVIVAL_AND_EMERGENCY_ASSISTANCE.md.
