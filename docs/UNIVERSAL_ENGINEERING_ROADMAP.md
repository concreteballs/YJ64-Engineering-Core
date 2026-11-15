# Universal Engineering Capability Roadmap

## Purpose

YJ64 Engineering Core is intended to become a general-purpose, model-independent engineering kernel. It must support the formulation, modelling, calculation, optimization, verification and manufacture of components and complete systems. Yacht engineering is an important application, not a hard-coded limit on the core.

The core should not claim that every discipline is already implemented. It provides stable contracts for specialist solvers and manufacturing systems, records their evidence and limitations, and makes missing capabilities explicit.

## 1. Common engineering project model

Every project, assembly, component, calculation and manufacturing artifact must be revisioned and traceable.

A component record should be able to reference:
- geometry and coordinate systems;
- material, material condition, heat treatment and manufacturing route;
- mass, centre of gravity and inertia;
- interfaces, joints, fits, tolerances and surface requirements;
- load cases, boundary conditions and operating environment;
- thermal, electrical, fluid, chemical and mechanical requirements;
- manufacturing constraints and available equipment;
- inspection, test and acceptance requirements;
- provenance, source revisions, assumptions, uncertainty and validation status.

A change to geometry, material, load, process or boundary conditions must invalidate dependent results and mark derived drawings, toolpaths and reports as stale. Every result must identify the exact input revisions it used.

## 2. Engineering disciplines and solver interfaces

The architecture should support independently installable and replaceable solvers for:

- statics, dynamics, kinematics and multibody mechanisms;
- beam, shell and solid structural analysis;
- strength, stiffness, buckling, fracture, fatigue and vibration;
- heat transfer, thermodynamics and thermal stress;
- fluid mechanics, hydrodynamics, aerodynamics and CFD;
- electromagnetics, electrical systems and power electronics;
- acoustics, resonance and noise;
- materials science, corrosion, wear, tribology and chemical compatibility;
- optimization, sensitivity, uncertainty and reliability analysis;
- control systems and system-level simulation.

Use explicit operation names, typed SI-unit inputs and outputs, solver/version metadata, bounded execution and structured warnings. A solver result is not automatically validated merely because a solver completed successfully.

## 3. Marine electronics, automation and moving-vessel environment

Marine electronics is a vessel-wide subsystem shared by navigation, propulsion, safety, communications and onboard robotics. It is not limited to robot electronics.

Cover radar, AIS, GNSS, chartplotters, sonar/echosounders, autopilot, heading and motion sensors, wind and speed instruments, communications, distress signalling, cameras, machinery sensors, embedded controllers, displays, data networks and power electronics. Integrate these with the electrical architecture, cable schedules, antennas/transducers, grounding, bonding, shielding, EMC and equipment-specific installation requirements.

Represent marine environmental qualification explicitly: ingress and immersion exposure, salt mist, corrosion, humidity, condensation, temperature and cold, vibration, shock, UV, electrical transients, interference and power interruption. Store sourced IP/environmental ratings and manufacturer limits rather than inferring protection.

Create a shared six-degree-of-freedom vessel-motion model (surge, sway, heave, roll, pitch, yaw), angular rates and accelerations, tied to sea-state scenarios and uncertainty. This model feeds instrument correction, autopilot/stabilization, equipment mounting, robotic balance and manipulation, and UAV launch/recovery. Define operational and degraded envelopes by sea state. A robot must be designed for a moving deck, not just static equilibrium.

## 4. Robotics, mechanisms and autonomous vehicles

Use a task-derived skeleton/chassis-first architecture. Define coordinate frames, links, joints, degrees of freedom, ranges, stiffness, load paths, mass, centre of gravity and inertia before selecting actuator muscles. Support humanoid and non-humanoid morphologies: wheeled, tracked, legged, manipulator, deckhand, rescue, inspection, galley and general-purpose robots.

Actuator choices must be technology-neutral and comparable: electric motor/gear drives, cable/tendon actuation, hydraulic and pneumatic systems, compliant/series-elastic transmissions, variable-stiffness systems and emerging electroactive/artificial-muscle materials where validated data exists. Record force/torque, stroke, speed, efficiency, power, thermal limits, bandwidth, compliance, fatigue, failure modes and maintenance. Do not treat speculative muscle materials as proven.

Marine robots require corrosion-resistant materials/coatings, sealing, drainage, salt and condensation protection, cold-weather operation, vibration/shock resistance, safe stowage, emergency stop and fail-safe behaviour. Their stability and manipulation must account for vessel motion and defined sea-state limits.

The same mechanism solvers should support robot joints and grippers, gears, linkages, bearings, clutches, brakes, cable/pulley systems, sailing and anchor winches, capstans, davits, crane beams and rescue-boat hoists. Winch sizing must include line pull, sheet/rope geometry, drum radius/capacity, gear ratio, efficiency, speed, holding brake, duty, fatigue, corrosion and dynamic vessel loads—not only nominal sail area or payload.

Support marine propellers and aerial rotors, keeping hydrodynamic and aerodynamic operating models distinct. Calculate thrust, torque, power, efficiency and operating envelope, with cavitation/ventilation for water and tip-speed, wind/gust and acoustic considerations for air. Match rotors/propellers to motors, engines, gearboxes, controllers and energy storage.

Support multirotor, fixed-wing, hybrid VTOL and larger cargo/rescue UAVs. Model mass, CG, inertia, aerodynamics, propulsion, energy, endurance, range, payload, control authority, wind response and failure modes. Include maritime delivery of distress beacons or communications payloads as a use case, subject to applicable aviation, maritime and radio requirements.

## 5. Verification for marine electronics, robots and vehicles

All new domains use common versioned components, solver contracts, material records, mass/power/thermal budgets, provenance and evidence states. Distinguish analytical screening, simulation, review, prototype, bench/field testing and qualification. Human-interacting robots, lifting systems, propellers and aircraft require appropriate hazard analysis, safeguards and independent verification; successful simulation is not certification.

## 6. Materials and material condition

The material knowledge layer must cover metals and alloys, polymers, elastomers, ceramics, glass, composites, sandwich structures, foams, adhesives, coatings and relevant construction materials.

Material records must distinguish nominal alloy/polymer identity from actual condition and product form. Where applicable, store:
- density and temperature-dependent physical properties;
- elastic, plastic, strength and fatigue properties;
- anisotropy and directional properties;
- fracture, creep, wear and corrosion data;
- thermal and electrical properties;
- product form, manufacturing process and standards designation;
- source, test method, temperature, orientation, condition and uncertainty.

Heat treatment is a process linked to a particular alloy, product form and target properties, not a generic label. The system must represent process stages, temperature/time profile, atmosphere or quench medium, cooling, aging, distortion risk, hardness and verification tests. It must not invent a universal heat-treatment cycle when alloy and condition are unknown.

## 7. Digital manufacturing and onboard production

Manufacturing is a first-class engineering domain, not a final file-export button.

### Polymer and composite additive manufacturing
Support process-specific material data, build orientation, layer strategy, anisotropy, infill, reinforcement, support strategy, shrinkage, warpage, environmental resistance and post-processing.

### Metal additive manufacturing
Provide interfaces for powder-bed fusion, directed-energy deposition and wire-fed processes where supported by the selected machine. Represent alloy/powder or wire specification, machine limits, build orientation, support strategy, process parameters, atmosphere, porosity and defect controls, residual stress, distortion, stress relief, heat treatment, hot isostatic pressing where applicable, machining allowance and inspection.

Do not infer that a generic STL is a validated metal-print job. Machine-specific build preparation and qualified process parameters are required.

### CNC machining and milling
Support stock selection, machining allowances, datum strategy, workholding, tool selection, cutting speed, feed, depth/width of cut, coolant, tool reach, collision checks, tolerances, surface finish and operation sequence. Generate machine-specific NC/G-code only after a specific machine, controller, tools, fixtures and postprocessor are selected and verified.

### CAD and manufacturing deliverables
Where the backend supports them, produce:
- editable native CAD and neutral STEP geometry;
- STL/3MF meshes for additive manufacturing;
- dimensioned drawings and GD&T;
- material and process specifications;
- inspection plans and measurement features;
- build files or CAM toolpaths;
- machine-specific NC/G-code only after postprocessor and setup validation;
- a manufacturing report tied to the exact component revision.

Manufacturing feasibility checks must include machine envelope, tolerances, minimum features, tool access, support removal, stock availability and post-processing access.

### Part criticality and evidence
Classify parts by consequence of failure and required assurance. Non-critical covers, brackets, sensor mounts and plugs may be candidates for onboard production after fit and environmental checks. Load-bearing, rotating, pressure-containing, engine-internal, steering, rigging, mast and safety-critical parts require appropriate qualified materials/processes, engineering verification, inspection and proof testing. The system must never mark a part safe solely because it can generate a printable file.

## 8. Design for repair and unavailable parts

The system should support reverse engineering from measurements, photographs, scans, samples and partial drawings. It should record measurement uncertainty and distinguish observed geometry from inferred geometry.

For a missing or obsolete part, workflow:
1. identify function, interfaces and operating conditions;
2. capture geometry and uncertainty;
3. identify original material and condition if possible;
4. establish load, temperature, speed, pressure, chemical and duty-cycle requirements;
5. compare redesign, repair, machining and additive-manufacturing routes;
6. calculate and simulate the proposed replacement;
7. define inspection and validation tests;
8. release a manufacturing package only at an explicitly stated evidence level.

This applies to small mechanisms and engine components as well as large structures. The core must not assume that visual similarity proves functional equivalence.

## 9. TRIZ and systematic invention support

Add a pluggable engineering knowledge and invention-support layer. TRIZ should be one method in a broader method library.

Initial method families:
- functional analysis and function-oriented search;
- technical and physical contradiction formulation;
- the 40 inventive principles and contradiction matrix;
- separation principles for physical contradictions;
- resource analysis and ideality;
- Su-Field (substance-field) analysis and standard solution patterns;
- ARIZ-style stepwise problem formulation;
- effects databases and cross-domain analogies;
- design-for-X methods: manufacture, assembly, maintenance, repair, reliability and cost.

The knowledge layer must use licensed or openly usable source material, retain attribution and version information, and avoid copying restricted books or databases without permission. Store concepts as structured, searchable records with source, scope, examples, caveats and links to the original material.

### Invention workflow

1. Describe the target function and measurable success criteria.
2. Map the current system, components, interactions and harmful/useful effects.
3. Identify the contradiction and available resources.
4. Generate multiple candidate concepts using selected methods.
5. Explain which principle or analogy produced each candidate.
6. Convert each candidate into a testable engineering hypothesis.
7. Screen for physical feasibility, safety, cost, mass, manufacturability and maintainability.
8. Route promising candidates to the appropriate CAD and physics solvers.
9. Compare results and preserve rejected concepts with reasons.

TRIZ output is a hypothesis generator, not proof. No proposed improvement should bypass physical modelling, independent review or testing when those are required.

## 10. Evidence and validation levels

Every artifact and result should carry a clear state, for example:
- concept;
- input data incomplete;
- analytical screening;
- numerical simulation;
- independently reviewed;
- prototype manufactured;
- bench tested;
- field tested;
- qualified/certified for a stated use.

Do not collapse these states into a single pass/fail badge. Record test conditions, instrumentation, calibration, acceptance criteria, failures and deviations.

## 11. Recommended implementation order

1. Stabilize the common versioned component/project schema and solver contracts.
2. Add material records, units, provenance, uncertainty and process-condition representation.
3. Add manufacturing capability and machine-profile schemas for polymer printing, metal additive manufacturing and CNC.
4. Add geometry validation, neutral CAD exchange, drawing and inspection artifacts.
5. Add solver adapters incrementally: structural FEM, thermal, multibody, fluid and electromagnetic domains.
6. Add manufacturing feasibility, process planning and machine-specific postprocessor boundaries.
7. Add TRIZ and engineering knowledge retrieval with source/licensing metadata.
8. Demonstrate the complete workflow on representative components of increasing criticality, including a small replacement part and a mechanism assembly.
9. Connect domain-specific design, visualization, content and commercial modules through versioned interfaces.

## 12. Non-negotiable architecture rules

- No arbitrary LLM-generated code execution in the core process.
- Specialist tools run in isolated, resource-bounded workers.
- No hidden material, load, process or cost assumptions.
- Unknown inputs remain unknown; the system asks for data or reports a bounded estimate.
- Every calculation states assumptions, limitations and uncertainty.
- Every manufacturing artifact is tied to a specific validated design revision and machine/process profile.
- Generated concept imagery is never treated as CAD geometry or engineering evidence.
- Safety-critical release requires the appropriate qualified review, inspection and tests.
