# YJ64 Engineering Core — Unified Development Plan

**Scope:** this plan applies only to `concreteballs/YJ64-Engineering-Core`, branch `main`. It defines the engineering-core capability and interfaces. Separate design, visualization, website/content and commercial repositories may consume these interfaces, but are not modified by this plan.

## Mission

Build a model-independent engineering system that can formulate problems, generate candidate concepts, model and calculate complete systems and individual components, optimize them, prepare manufacturing data, and track evidence from analysis through physical testing.

The yacht is the first major application domain, not the limit of the engineering core. The system must eventually handle complete assemblies and very small replacement parts, including parts no longer commercially available.

This is a staged roadmap. A capability listed below is a target until its implementation, tests and validation evidence exist.

## Shared rules for every work package

- One versioned project/component model with stable identifiers and explicit units (SI internally).
- Every input, geometry, material, load case, solver result, drawing and manufacturing file is tied to exact revisions and provenance.
- A changed upstream input invalidates dependent calculations and marks drawings, renders, toolpaths and reports stale.
- Missing data remains explicitly unknown; no invented material properties, loads, process settings, prices or safety margins.
- Every result states method, solver/version, assumptions, uncertainty, warnings and limitations.
- Distinguish concept, analytical estimate, numerical simulation, reviewed design, manufactured prototype, tested part and qualified/certified use.
- Run CAD, FEM, CAM and other external tools in isolated, resource-limited workers. Never execute arbitrary LLM-generated code in the core process.
- A generated file is not proof that a part is safe or manufacturable. Safety-critical release requires the applicable engineering review, inspection and testing.

# Work packages

## Package 1 — Universal engineering kernel and common data model

**Build together:** project/component/assembly schemas, solver contracts, dispatcher, artifact/provenance model and validation states.

The common component schema must support:
- geometry references, coordinate frames, interfaces and assembly relationships;
- material, product form, material condition and heat-treatment state;
- mass, centre of gravity and inertia;
- loads, boundary conditions, operating states and environmental exposure;
- fits, tolerances, surface finish and inspection requirements;
- electrical, thermal, fluid, chemical and mechanical interfaces;
- manufacturing constraints, machine profiles and maintenance requirements;
- source references, assumptions, uncertainty and test evidence.

Create a plugin contract for specialist solvers and external applications. Inputs and outputs use typed SI values and explicit operation names. Solver completion is not the same as engineering validation.

## Package 2 — Physics and engineering solver platform

**Build the common interfaces and initial useful solvers as one coordinated block; add specialist solvers incrementally.**

Domains to support:
1. Structural mechanics: statics, dynamics, beams, shells, solids, joints, contact, buckling, fracture, fatigue and failure.
2. Mechanisms: kinematics, multibody dynamics, actuators, cables, pulleys, gears, linkages, folding and locking mechanisms.
3. Fluid engineering: hydrostatics, hydrodynamics, aerodynamics, CFD interfaces, resistance, lift/drag, cavitation, ventilation, pumps, pipes and heat exchangers.
4. Thermal engineering: conduction, convection, radiation, thermal expansion, thermal stress, cooling and refrigeration.
5. Electrical and electronic engineering: DC/AC networks, power electronics, motors, generators, batteries, protection, grounding/bonding, control and electromagnetic compatibility.
6. Controls and automation: sensors, actuators, feedback, fault states, interlocks and system simulation.
7. Vibrations, modal analysis, resonance, acoustics and noise.
8. Materials behaviour, corrosion, galvanic couples, wear, friction, tribology and chemical compatibility.
9. Optimization, sensitivity, uncertainty, reliability and system-level trade studies.

Support both analytical calculations and external numerical engines. Keep low-order screening models clearly distinguished from CFD, full FEM, certified calculations and test evidence.

## Package 3 — Materials, processes and manufacturing

**Build the material/process data model and manufacturing interfaces together**, because material properties depend on product form, process, orientation and treatment.

### Material knowledge
Cover marine aluminium and other alloys, steels, titanium and other metals, polymers, elastomers, ceramics, glass, fibre composites, sandwich/honeycomb structures, foams, adhesives, coatings and relevant construction materials. Wood is not a target hull material in the current project brief.

Store density, elastic/plastic properties, strength, fatigue, fracture, creep, wear, corrosion, thermal/electrical properties and anisotropy where relevant. Each property needs a source, test method, temperature, orientation, condition and uncertainty.

### Additive manufacturing
- Polymer and composite printing: polymer grade, reinforcement, build orientation, layer strategy, anisotropy, infill, supports, shrinkage, warpage and post-processing.
- Metal printing: powder-bed fusion, directed-energy deposition and wire-fed processes where supported; alloy and feedstock condition, machine limits, build orientation, process parameters, atmosphere, porosity/defect controls, residual stress, distortion, stress relief, heat treatment, HIP where applicable, machining allowance and inspection.
- Machine-specific build preparation must be separate from generic STL/3MF export. Never invent qualified machine parameters.

### CNC milling and machining
Represent stock, datums, fixtures, tools, tool reach, cutting speed, feed, depth/width of cut, coolant, collision checking, tolerances, surface finish and operation sequence. Generate machine-specific NC/G-code only after the exact machine, controller, tools, setup and verified postprocessor are known.

### Heat treatment
Model heat-treatment routes by alloy, product form and target condition: process stages, temperature/time profile, atmosphere, quench medium, cooling, aging, distortion risk, hardness and verification tests. Never offer a universal cycle when the alloy and condition are unknown.

### Deliverables
Where supported: editable native CAD, STEP, STL/3MF, dimensioned drawings with GD&T, material/process specification, inspection plan, CAM/build preparation, and machine-specific NC/G-code after setup verification. Track the exact revision and process profile for every artifact.

## Package 4 — Complete electrical power and energy engineering

**This is a major first-class engineering subsystem, not just a battery calculator.** It must design and verify the complete vessel electrical architecture.

### Voltage architectures to compare
Evaluate nominal DC architectures of **12 V, 24 V and 48 V** as explicit alternatives. Do not choose one in advance. Compare:
- current and cable cross-section for each load and distribution path;
- voltage drop, losses, heating and connector ratings;
- device availability and compatibility;
- converters and distribution complexity;
- battery configuration, protection and serviceability;
- peak loads, motor starting/surge currents and expansion capacity.

A mixed architecture may be appropriate (for example, a higher-voltage main bus with DC-DC conversion for lower-voltage consumers), but must be justified by the load inventory and actual equipment. Also model the vessel's AC system, shore supply, inverter and generator where applicable; frequency and shore standards depend on intended operating region.

### Energy sources and storage
Model solar panels by location, area, orientation, shading, temperature and realistic yield; MPPT/controllers; alternators; shore chargers; generators; wind or hydro generation where applicable; batteries by chemistry and configuration; BMS; fuses/contactors; DC-DC converters; inverters and chargers.

### Loads
Create a complete load register with rated power, voltage, duty cycle, start/surge demand, daily operating hours, priority and operating scenario. Include refrigeration/freezers, lighting, navigation, communications, radar, autopilot, computers, pumps, watermaker/desalination, ventilation, heating/cooling, galley appliances, entertainment, workshop tools and electric propulsion/charging where selected.

### Calculations and outputs
- daily and seasonal energy balance, autonomy and reserve;
- charge/discharge profiles and source contribution;
- battery usable energy, current, temperature and ageing assumptions;
- peak and continuous bus currents;
- cable sizing, voltage drop, thermal loading and routing;
- fuse/breaker ratings, interrupt capacity and selective coordination;
- short-circuit and fault analysis;
- isolation, grounding/earthing, bonding, leakage and galvanic-corrosion control;
- AC inverter sizing, waveform, frequency, shore connection and protective devices;
- monitoring, alarms, emergency isolation, redundancy and failure scenarios;
- single-line diagrams, circuit schedules, cable lists, protection schedule and equipment specifications.

Electrical design must account for the actual hull material and bonding strategy. Metallic and composite hulls have different bonding and isolation implications. Salt water is a conductive electrolyte; ingress, leakage paths, galvanic couples and corrosion must be modelled as real marine hazards.

Use applicable current small-craft standards and regulations as design constraints, including the relevant editions of ISO 13297 (AC/DC systems) and ISO 10133 (extra-low-voltage DC installations), plus applicable flag-state, equipment and classification requirements. Standards are controlled references, not text to reproduce without permission.

## Package 5 — Marine environment and complete vessel engineering

Build the vessel domain as a complete interacting system, not a hull-only model.

### Marine environment properties
Do not use one fixed “water density” for every calculation. Support water temperature, salinity and pressure and calculate/select density and other required properties from a traceable seawater model or measured inputs. Include viscosity, heat capacity, thermal conductivity, vapour pressure, freezing behaviour and electrical conductivity where relevant.

Typical seawater density is around 1025 kg/m³, while freshwater is around 1000 kg/m³; actual seawater density changes with temperature, salinity and pressure. This affects displacement and hydrostatics. Conductivity and chloride content also matter for corrosion, electrical leakage and material selection. Keep these effects distinct rather than treating “salt water” as one correction factor.

### Hydrostatic pressure and hull structural strength

Hydrostatics must feed structural load cases, not stop at displacement. For each operating/loading condition, calculate the external hydrostatic pressure field from local depth, water density and gravity, and the relevant internal pressure/reference level. For a vented hull with approximately atmospheric internal pressure, use the external-to-internal differential pressure on the wetted shell; do not mistake absolute ambient pressure for the net shell load. Pressure varies with depth and must be mapped over the actual hull geometry and waterline.

Use these pressure fields to define local panel and global structural cases for bottom and side shell plating/laminates, stiffeners, frames, floors, bulkheads, cross-structure and joints. Couple them with hull-girder bending/torsion, payload and tank loads, support reactions, wave-induced loads, slamming and local impact where applicable. Evaluate deflection, stress/strain, buckling, fatigue and failure modes using material/process-specific properties and appropriate shell/solid FEM or validated analytical methods. Account for openings, penetrations, bonded joints, laminate direction/thickness, core shear and skin wrinkling in sandwich construction.

The model must distinguish static hydrostatic pressure in displacement mode from dynamic pressure, slamming, impact, grounding and pressure loads on sealed compartments. A simplified pressure calculation is a load generator/screening step, not a complete scantling rule or class approval. The weight of the vessel is not a single downward force carried by the bottom: buoyancy arises from the distributed pressure field, while structural response depends on geometry, supports, internal structure and all load paths.

### Automated sail handling and remote yacht operation

Treat sail handling as a complete electromechanical and control system. Evaluate a self-tacking headsail on a track/carriage so routine tacks do not require a crew member to move and reattach the sheet; calculate track loads, carriage travel, sheet geometry, lead angles, end stops, damping, locking and failure states. Include an automatically furling headsail. For the mainsail, evaluate in-boom furling as a primary option, including boom structure, drum/mandrel, luff/foot geometry, sail compatibility, drive torque, alignment, jamming detection, manual recovery and safe reefing. Also retain in-mast furling as an optional configuration because it is widely used, but model its distinct mast structural, sail-shape, luff-tension, alignment and jam/recovery constraints. Do not assume either furling architecture is failure-proof.

Design an integrated remote-command capability that can operate the yacht from a smartphone as a low-cost user interface, while remaining expandable to dedicated marine displays, helm controls, certified autopilot equipment, redundant sensors and professional communications. The phone is an interface/secondary terminal, not the sole safety controller. Propulsion, steering, sail winches/furlers, power management and safety interlocks remain under local onboard controllers with deterministic fail-safe behaviour. Provide distinct authority levels: monitoring, supervised command, limited autonomous navigation and approved autonomous passage. Require explicit mode indication, command acknowledgement, position/heading/speed feedback, geofencing, obstacle/traffic awareness, collision-risk handling, weather/sea-state limits, route constraints, watchdogs, emergency stop/override and safe response to lost or delayed communications.

Support motor-only remote passage as the first operational mode. Sailing automation is a separately validated mode and must only be enabled with a compatible rig configuration, including self-tacking headsail and automated furling/reefing arrangements. Define safe sail reduction, depowering and storm-response procedures; never infer that automated furling alone makes a yacht safe in severe weather.

A future use case is owner-directed repositioning: the yacht may leave an exposed or insecure anchorage, travel to a pre-authorized offshore waypoint (the owner suggested approximately 200 km from shore as an example), enter a defined low-energy waiting state, then receive a new route and rendezvous with the owner at another authorized location. Model this as a sequence of bounded mission states, not an unrestricted “send it anywhere” command. “Wait” must be explicitly selected among safe alternatives such as controlled drifting within a verified area, heave-to under a validated sail plan, or station-keeping if propulsion/energy permits. Include drift prediction, current/wind forecasts and uncertainty, exclusion zones, minimum separation from traffic, shallow water and hazards, energy reserve for diversion/recovery, anchor/no-anchor logic, and periodic health checks. An offshore waypoint is not inherently safe merely because it is far from shore.

Autonomous or remotely supervised operation must be evaluated against applicable COLREGs, flag-state and coastal-state rules, radio/satellite licensing, navigation equipment requirements and insurance/class constraints. The system must not represent remote operation as legally permitted everywhere. Loss of shore link must not disable onboard collision avoidance, navigation safety or emergency procedures; define local fallback behaviour for each failure mode.

### Whole-vessel subsystems
- twin hulls, crossbeams, decks, bulkheads, frames, stringers and structural joints;
- hull material alternatives: marine aluminium, glass-fibre composite, carbon composite, sandwich/honeycomb and reinforced concrete as a special comparison;
- hydrostatics, displacement, reserve buoyancy, trim, heel, stability, downflooding and loading cases;
- foils, rudders, steering, appendages, slamming, cavitation and ventilation;
- mast, boom, sails, standing/running rigging, fittings and folding/stowage mechanisms;
- propulsion alternatives: diesel, electric and hybrid; engines, motors, batteries, shafts, saildrives/pods, propellers, cooling, fuel and exhaust;
- anchors, chain, windlass, deck equipment and mooring;
- accommodation, cabins, berths, galley, refrigeration, furniture, storage and appliances;
- fresh-water, grey-water, black-water, fuel and other tanks, pumps, plumbing and desalination;
- safety systems, bilge, fire protection, communications and navigation;
- payload, provisions, maintenance access, service clearances and operating costs.

Maintain subsystem mass, centre of gravity, power, cooling, volume, access and maintenance budgets. Avoid double counting and evaluate empty, design-load and maximum-load scenarios. The design must account for the complete yacht, not merely the hull and rig.

## Package 6 — Marine electronics, instrumentation and vessel automation

**Treat electronics as a vessel-wide engineering discipline shared by the yacht, robots and autonomous craft—not as a subfeature of robotics.**

Cover the complete marine electronic architecture and its interfaces to the electrical power package:

- navigation sensors and systems: GNSS, heading sensors, magnetic and satellite compasses, inertial measurement units, speed/log, wind instruments, depth sounders and sonar;
- radar, AIS, chartplotters, multifunction displays, autopilot, communications, distress and emergency signalling;
- cameras, thermal/low-light imaging, microphones, environmental and machinery sensors;
- onboard networks, data buses, gateways, time synchronization, signal integrity, antenna placement and electromagnetic compatibility;
- embedded controllers, compute units, software interfaces, alarms, logging, redundancy, cybersecurity boundaries and degraded operating modes;
- transducers, connectors, cable routing, shielding, grounding, bonding, isolation and power conditioning;
- equipment selection and integration using actual manufacturer specifications, interface protocols, operating limits and installation requirements.

### Marine environmental qualification

Every electronic device and installation must be evaluated for its actual location and duty: water ingress and immersion exposure, salt mist/corrosion, condensation, humidity, temperature range, vibration, mechanical shock, continuous vessel motion, UV exposure where relevant, electrical transients, conducted/radiated interference and power interruptions. Represent ingress-protection and environmental ratings as sourced equipment data; do not infer them from product category.

### Vessel motion and operation at sea

The system must model six-degree-of-freedom vessel motion (surge, sway, heave, roll, pitch and yaw), angular rates and accelerations, with operating sea-state scenarios and uncertainty. Use this common motion/environment model for:
- instrument and antenna mounting, sensor alignment and measurement correction;
- autopilot, stabilization and control-system evaluation;
- robotic balance, foot placement, grasping and manipulation on a moving deck;
- machinery, battery, tank, payload and equipment mounting loads;
- launch/recovery and operation of drones and rescue equipment from a moving vessel.

A robot intended for deck work must be designed and tested for a moving support frame, not merely for static balance. It needs motion sensing, state estimation, control bandwidth and recovery/fail-safe behaviour appropriate to the defined sea-state envelope. Define what operations are permitted, degraded or prohibited at each sea state; do not promise safe operation in arbitrary storms.

### Separate design-time vessel dynamics from real-time onboard learning

These are complementary models and must not be conflated.

**Design-time naval architecture and hull hydrodynamics:** calculate how hull geometry and loading interact with waves, speed and heading. The model must support hydrostatics, resistance, seakeeping and six-degree-of-freedom response, wave encounter conditions, response amplitude operators (RAOs) where data/methods permit, added mass, damping, restoring forces, slamming and relevant structural loads. It must predict and compare candidate hull forms over defined operating conditions. A short rolling sensor history from one voyage cannot replace this design-time analysis or establish performance in unobserved sea states.

**Onboard adaptive motion estimation for robots:** do not expect one fixed sea-motion profile to predict every changing wave pattern. A robot may use a smartphone as a replaceable onboard computing, communications and sensor package. It can provide phone calls where cellular coverage exists, and expose available sensors such as accelerometer, gyroscope, magnetometer, GNSS and barometer where supported. Sensor availability, sample rate, calibration, orientation, latency and drift must be measured rather than assumed. The phone must be rigidly mounted in a known frame; critical balance/control should also be able to use dedicated robot IMU/joint/foot-contact sensors if phone measurements are insufficient or unavailable.

Use a configurable rolling local observation window (initial candidates: 5 or 15 minutes, not a fixed universal choice) to estimate recent motion statistics and short-horizon motion tendencies. Continuously update the estimate as new measurements arrive; track confidence and prediction error, detect abrupt regime changes, and fall back to a safe degraded mode when sensors or predictions become unreliable. This is adaptive short-horizon estimation, not guaranteed prediction of future waves. The control system must react to measured motion as well as anticipate it.

**Data retention and privacy:** raw high-rate motion samples should remain in volatile/local working memory only for the configured rolling window and be automatically overwritten/deleted as the window advances. Do not create a persistent onboard archive of raw motion history. If the owner explicitly enables remote research/diagnostics, upload only a separately defined, minimized set of derived statistics or selected records, with consent, encryption, access control, retention limits and the ability to disable upload. Remote storage is optional and must never be required for real-time robot balance or safe operation. Loss of internet/cellular service must not interrupt local estimation or control.

Record the algorithm version, sensor configuration, window length, uncertainty, prediction error and sea-state context with any uploaded aggregate so that datasets remain interpretable. Avoid retaining identifiable crew/location data unless strictly necessary and explicitly authorized.

### Outputs

Provide network and interface diagrams, equipment and sensor registers, antenna/transducer installation constraints, cable and power schedules, data-flow maps, alarm/failure matrices, environmental qualification requirements and traceable integration test plans.

## Package 7 — Robotics, mechanisms and autonomous vehicles

**Use a common mechanical and control foundation for humanoid robots, specialist robots, lifting equipment, winches, propellers and aerial vehicles.**

### Skeleton-first and modular actuation architecture

Start with a task-derived mechanical chassis/skeleton: coordinate frames, links, joints, degrees of freedom, ranges, limits, stiffness, backlash, load paths, mass, centre of gravity and inertia. Only then select and attach actuator “muscles” and transmissions to meet required forces, speed, power, compliance, precision, duty cycle and environmental conditions.

Do not assume electric motors are the only or universally best actuator. Compare:
- electric motors, geared drives and direct drives;
- cable/tendon and remote-actuation systems;
- hydraulic and pneumatic actuators;
- compliant and elastic transmissions, series-elastic actuators and variable-stiffness mechanisms;
- electroactive polymers and other emerging artificial-muscle technologies where reliable property data exists.

For every actuator, model force/torque, stroke, speed, power, efficiency, thermal limits, bandwidth, compliance, fatigue life, failure modes, energy supply and maintenance. Distinguish demonstrated technologies from speculative materials; unknown properties remain unknown.

### Robot families and marine requirements

Support humanoid, mobile, wheeled, tracked, legged, manipulator, service, inspection, cooking/galley, deckhand, rescue and general-purpose configurations. The design workflow must choose morphology from the task and environment rather than forcing every robot into a human shape.

Marine robot configurations must explicitly address corrosion-resistant materials and coatings, sealed joints/connectors, drainage, salt ingress, condensation, cold-weather operation, vibration, shock, washdown and serviceability. For onboard robots, integrate vessel motion and sea-state models from Package 6. Include balance and manipulation on moving decks, handholds/anchoring strategies, safe stowage, emergency stop and safe behaviour after loss of power or communications.

### Mechanisms, winches and lifting systems

Provide reusable solvers for gears, belts, chains, screws, linkages, bearings, clutches, brakes, cable drives, pulleys and reeving. Apply them to:
- sailing winches sized from sail loads, sheet geometry, line lead, drum radius, gear ratio, handle/drive input, efficiency, duty and braking/holding requirements;
- anchor and mooring winches, capstans and windlasses;
- davits, crane beams, boat/rescue-craft hoists and other lifting systems;
- robot joints, grippers, manipulators and deployable structures.

Calculate line pull, torque, speed, power, drum capacity, rope fleet angle, line layering, brake/holding capacity, structural reactions, fatigue and dynamic loads. Include vessel motion, shock loading, corrosion and applicable safety factors/standards as explicit inputs. Never size a lifting device from nominal payload alone.

### Propellers and rotors

Support marine propellers and aerial rotors with geometry, blade count, diameter, pitch/twist, section data, material, rotational speed and operating medium. Calculate thrust, torque, power, efficiency and operating envelope; add cavitation, ventilation, tip-speed, structural, vibration and noise checks as appropriate. Keep air and water models physically distinct while reusing geometry, blade-element and rotating-machinery infrastructure where valid. Include propeller/rotor matching to motors, engines, shafts, gearboxes, controllers and energy systems.

### Uncrewed and aerial vehicles

Support multirotor, fixed-wing, hybrid VTOL and other UAV configurations, including larger cargo/rescue platforms. Model mass budget, centre of gravity, inertia, aerodynamics, propulsion, rotor/propeller performance, battery/fuel energy, endurance, range, payload, control authority, wind/gust response, take-off/landing and failure cases. Include maritime rescue use cases such as delivering a distress beacon or communications payload to another vessel, subject to aviation, maritime and radio regulations.

### Verification

Robot and vehicle outputs must include kinematic reach/workspace, collision checks, load and stability envelopes, actuator sizing, energy budget, thermal limits, fault response, maintenance access and test plans. Separate simulation from physical validation. Human-interacting and load-bearing systems require appropriate risk assessment, guarding, emergency stops and independent testing.

### Small underwater inspection and service ROVs

Include a dedicated design path for compact remotely operated underwater vehicles (ROVs), initially targeting a 15–20 m operating depth for yacht maintenance and recovery support. Representative tasks include inspecting the anchor, chain and seabed around a fouled anchor; inspecting hull bottoms, rudders, propellers, foils and intakes; locating entanglements; and performing limited non-destructive service tasks. Treat anchor recovery as inspection/assistance, not an assumption that a small ROV can safely lift or free a loaded anchor or chain.

Model the vehicle as a complete system: pressure-resistant electronics/battery enclosures and end closures; penetrators, connectors and tether; cameras, lights and optional sonar; thrusters and guards; buoyancy/ballast and trim; frame, lifting points and tether management; control, navigation aids and communications; optional manipulator/tooling; power, thermal management, leak detection and emergency recovery. Evaluate hydrodynamic drag, tether drag/current loads, stability, controllability, thrust margin, endurance, visibility, handling and recovery from loss of power or tether communication.

At 15–20 m, calculate ambient pressure and differential pressure for each sealed volume using actual water density and depth. Pressure-vessel design must address external-pressure collapse/implosion, shell geometry and thickness, end-cap restraint, penetrator stress concentrations, seals, buckling imperfections, material properties, manufacturing tolerances, fatigue/cycles and proof/leak testing. A nominal depth rating is a verified design and test requirement, not a label inferred from component marketing. Pressure housings, battery enclosures and connectors require independently substantiated ratings; buoyancy materials must be qualified for depth and water absorption.

The first target is a tethered inspection ROV with camera, lighting, controlled thrusters and depth/heading feedback. Manipulation and anchor/chain intervention are later capability levels, requiring explicit force limits, tool design, tether/vehicle reaction analysis and hazard controls. The 15–20 m target is an initial product envelope, not a claim of achieved capability or certification.

## Package 8 — Invention methods and engineering knowledge base

**Create a unified method library rather than choosing only one TRIZ variant.**

Include:
- classical TRIZ: contradictions, 40 inventive principles, contradiction matrix, separation principles, Su-Field analysis, standards, evolution trends and ARIZ;
- USIT (Unified Structured Inventive Thinking), developed by Ed Sickafus in the United States at Ford, as a concise structured problem-solving method influenced by TRIZ;
- SIT/ASIT (Systematic/Advanced Systematic Inventive Thinking), while recording its distinct historical origin and relationship to TRIZ/USIT;
- functional analysis, resource analysis, ideality and function-oriented search;
- morphological analysis and morphological charts;
- C-K design theory, design-by-analogy and biomimicry;
- QFD and requirements engineering;
- FMEA/FMECA, HAZID/HAZOP, fault trees and reliability-centred maintenance;
- design-for-manufacture, assembly, service, repair, cost, safety and sustainability.

Every method/knowledge record must retain source, author, edition, license/usage rights, scope and limitations. Do not ingest or redistribute copyrighted books or proprietary databases without permission.

### Candidate-improvement workflow
1. Define the required function and measurable success criteria.
2. Map system elements, interfaces, useful/harmful effects and constraints.
3. Identify technical/physical contradictions and available resources.
4. Generate multiple candidate concepts using several methods.
5. Explain the method and assumptions behind each proposal.
6. Convert candidates into testable engineering hypotheses.
7. Screen for physical feasibility, safety, reliability, cost, mass and manufacturability.
8. Send candidates to the appropriate CAD and physics solvers.
9. Compare results, preserve rejected ideas and record why they were rejected.

Invention methods generate hypotheses; they do not prove feasibility.

## Package 9 — Reverse engineering, repair and component lifecycle

Support repair and reproduction of unavailable parts, from small engine components to structural assemblies.

Inputs may include measurements, photographs, scans, broken samples and incomplete drawings. Record measurement uncertainty and distinguish observed geometry from inferred geometry.

Workflow:
1. identify function, interfaces and operating conditions;
2. capture geometry and uncertainty;
3. identify original material, condition and process where possible;
4. define mechanical, thermal, electrical, pressure, speed, chemical and duty-cycle requirements;
5. compare repair, redesign, machining and additive routes;
6. model and verify the proposed replacement;
7. define inspection and validation tests;
8. release the manufacturing package at a clearly stated evidence level.

Classify part criticality. Sensor brackets, instrument housings, covers and plugs may be suitable for onboard production after checks. Mast, rigging, steering, engine-internal, pressure-containing, rotating and other safety-critical components require qualified materials/processes, engineering review, inspection and appropriate proof tests. A printable file is never an automatic approval.

## Package 10 — Specialized design and mechanism pilots

Once the common kernel and relevant solvers exist, use real projects as integration tests. The folding mast is a future pilot, not a prerequisite for building the general system.

The saved concept notes include a mast folding in two or three stages depending on height, plus a separately folding/rolling arrangement using cross-shaped supports at bends with a cable passing through them. Do not invent missing geometry or mechanism details. When drawings are available, decompose and analyze mast sections, hinges, locks, cable path, actuation, rigging release/re-tensioning, stowage supports, vessel loads, transition loads, fail-safe states and operational interlocks.

## Package 11 — Visualization and simulation presentation interface

A separate visualization module should consume the same versioned geometry and engineering data. Provide interfaces for:
- accurate CAD-based still renders and technical illustrations;
- assembly/exploded views and cutaways;
- animation from actual mechanism/kinematic simulation;
- engineering plots, flow/force visualizations and simulation playback;
- concept imagery for communication and marketing.

Keep accurate CAD/solver visualization distinct from generative concept images. Concept imagery must never be presented as validated geometry or engineering evidence. The same outputs can later support a project website.

## Package 12 — Website/content and commercial workflows (later)

The engineering core should expose approved, versioned artifacts and descriptions to downstream agents.

A content agent may prepare website text, images, video/audio assets, upload media, fill platform forms and publish when explicitly authorized. A separate commercial module may later handle market analysis, positioning, marketing strategy, advertising, promotion, audience development and sales. These are downstream workflows, not reasons to put marketing logic inside the engineering kernel.

# Recommended execution sequence and grouping

To minimize repeated work, implement in these combined passes:

1. **Foundation pass:** Package 1 plus the shared evidence/versioning rules. Establish contracts before adding many solvers.
2. **Core physics pass:** Package 2 solver interfaces and first implementations, including the electrical-network foundation.
3. **Materials and manufacturing pass:** Package 3 together with the manufacturing fields in Package 1. Material/process data must be consistent with solver and CAD records.
4. **Electrical vessel pass:** Complete Package 4 as a coherent subsystem, then connect its mass, heat, space, control and safety interfaces to Package 5.
5. **Marine/vessel integration pass:** Package 5, using existing hydrostatics, mass-budget, flow and hull-material work as starting points; expand the simplified models instead of treating them as finished naval architecture.
6. **Marine electronics and automation pass:** Package 6, integrated with vessel power, motion, navigation and communications.
7. **Robotics and mechanisms pass:** Package 7, starting with reusable kinematics, actuator models, winches and propellers before complete robots and UAVs.
8. **Invention and repair pass:** Packages 8 and 9. Connect idea generation to actual solvers and manufacturing feasibility, not just text suggestions.
9. **Pilot validation pass:** Package 10 with real mechanisms/components; the folding mast can be one when its drawings are available.
10. **Visualization pass:** Package 11 against versioned design and simulation data.
11. **Downstream publishing/commercial pass:** Package 12 after reliable engineering outputs and approvals exist.

Packages 2–7 can be developed by parallel contributors only after Package 1 contracts are stable. Integration and validation remain centralized in the core repository.

## Current implementation versus target

Already present in the repository are early foundations for dispatch/pipeline contracts, CAD adapters, flow/aero/hydro screening, sail polars and material screening, apparent wind, simplified twin-hull hydrostatics, vessel mass budgeting and hull material mass/cost/maintenance screening.

These are starting points, not completed full-discipline engineering systems. In particular, the current hydrostatics is not a full stability analysis, the current structural adapter is not hull FEM, coefficient-based flow models are not CFD, and the current hull material comparison is not structural equivalence sizing. Future work must preserve these distinctions.
