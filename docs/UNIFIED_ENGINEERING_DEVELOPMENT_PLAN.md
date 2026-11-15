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

## Package 6 — Invention methods and engineering knowledge base

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

## Package 7 — Reverse engineering, repair and component lifecycle

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

## Package 8 — Specialized design and mechanism pilots

Once the common kernel and relevant solvers exist, use real projects as integration tests. The folding mast is a future pilot, not a prerequisite for building the general system.

The saved concept notes include a mast folding in two or three stages depending on height, plus a separately folding/rolling arrangement using cross-shaped supports at bends with a cable passing through them. Do not invent missing geometry or mechanism details. When drawings are available, decompose and analyze mast sections, hinges, locks, cable path, actuation, rigging release/re-tensioning, stowage supports, vessel loads, transition loads, fail-safe states and operational interlocks.

## Package 9 — Visualization and simulation presentation interface

A separate visualization module should consume the same versioned geometry and engineering data. Provide interfaces for:
- accurate CAD-based still renders and technical illustrations;
- assembly/exploded views and cutaways;
- animation from actual mechanism/kinematic simulation;
- engineering plots, flow/force visualizations and simulation playback;
- concept imagery for communication and marketing.

Keep accurate CAD/solver visualization distinct from generative concept images. Concept imagery must never be presented as validated geometry or engineering evidence. The same outputs can later support a project website.

## Package 10 — Website/content and commercial workflows (later)

The engineering core should expose approved, versioned artifacts and descriptions to downstream agents.

A content agent may prepare website text, images, video/audio assets, upload media, fill platform forms and publish when explicitly authorized. A separate commercial module may later handle market analysis, positioning, marketing strategy, advertising, promotion, audience development and sales. These are downstream workflows, not reasons to put marketing logic inside the engineering kernel.

# Recommended execution sequence and grouping

To minimize repeated work, implement in these combined passes:

1. **Foundation pass:** Package 1 plus the shared evidence/versioning rules. Establish contracts before adding many solvers.
2. **Core physics pass:** Package 2 solver interfaces and first implementations, including the electrical-network foundation.
3. **Materials and manufacturing pass:** Package 3 together with the manufacturing fields in Package 1. Material/process data must be consistent with solver and CAD records.
4. **Electrical vessel pass:** Complete Package 4 as a coherent subsystem, then connect its mass, heat, space, control and safety interfaces to Package 5.
5. **Marine/vessel integration pass:** Package 5, using existing hydrostatics, mass-budget, flow and hull-material work as starting points; expand the simplified models instead of treating them as finished naval architecture.
6. **Invention and repair pass:** Packages 6 and 7. Connect idea generation to actual solvers and manufacturing feasibility, not just text suggestions.
7. **Pilot validation pass:** Package 8 with one or more real mechanisms/components; the folding mast can be one when its drawings are available.
8. **Visualization pass:** Package 9 against versioned design and simulation data.
9. **Downstream publishing/commercial pass:** Package 10 after reliable engineering outputs and approvals exist.

Packages 2–6 can be developed by parallel contributors only after Package 1 contracts are stable. Integration and validation remain centralized in the core repository.

## Current implementation versus target

Already present in the repository are early foundations for dispatch/pipeline contracts, CAD adapters, flow/aero/hydro screening, sail polars and material screening, apparent wind, simplified twin-hull hydrostatics, vessel mass budgeting and hull material mass/cost/maintenance screening.

These are starting points, not completed full-discipline engineering systems. In particular, the current hydrostatics is not a full stability analysis, the current structural adapter is not hull FEM, coefficient-based flow models are not CFD, and the current hull material comparison is not structural equivalence sizing. Future work must preserve these distinctions.
