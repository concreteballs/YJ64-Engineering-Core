# YJ64 Engineering Core — architecture

## System responsibilities

- Consortium / application: design discussion, project state, permissions, routing and revision history.
- Vision-capable model: interprets sketches, photographs and markup; returns observations tied to image coordinates.
- Yacht CAD service: owns validated parametric hull geometry and generates editable 2D/3D artifacts.
- Physics service: consumes versioned geometry, operating conditions, materials and loads through bounded solver adapters.
- Commercial agent: evaluates manufacturing and lifecycle cost using traceable engineering inputs.
- Independent oversight: reviews assumptions, evidence and proposed real-world actions.

## Hull geometry contract

The initial design target is a single monohull outer envelope represented by ordered longitudinal stations. Each station defines x position, half-beam, keel height, chine height and deck-edge height in SI metres. The section profile is a simple five-point chine shape. The same validated hull drives SVG plan/profile/sections, editable OpenSCAD source, a FreeCAD loft macro and optional OpenSCAD STL rendering.

The 2D view is a preliminary technical sketch, not a manufacturing drawing. The 3D model is the outer hull envelope only; it does not yet contain frames, stringers, bulkheads, laminate, plate thickness or scantlings.

## Design iteration and image input

Natural-language interpretation is separated from geometry mutation:
1. The language model proposes a structured change operation.
2. apply_hull_changes accepts only whitelisted operations: set_station, scale_beam, translate_vertical and rename.
3. The updated station data is revalidated.
4. A before/after parameter record is returned.
5. CAD artifacts are regenerated from the new parameter set.

Visual collaboration uses image hashes, normalized markup and structured observations. The image module does not itself perform semantic image recognition. A vision-capable model must inspect the picture and return observations. Ambiguous observations must be clarified rather than silently changing geometry.

## Dispatcher and pipeline

EngineeringDispatcher requires explicit operation names. CAD backends may return multiple ArtifactReference values. EngineeringPipeline supports CAD-only exploration and CAD plus an explicit physics operation. A branch failure must not suppress the other branch. Completed CAD generation does not imply physical validity. Each dispatched result records a SHA-256 input digest over the canonical request and selected operation. ComponentCalculationRecord can pin that result to exact component revisions; stale_calculations identifies records whose dependencies changed or disappeared. This is a traceability primitive; persistent project storage, transitive invalidation and automatic reruns remain future work.

## Catamaran displacement and mass budget

The hydrostatics screening solver integrates each of two station-defined hull envelopes at explicit design and maximum waterlines. It reports geometric displaced volume, mass and reserve volume. This is not a stability or load-line solver; the chosen maximum waterline is not a certified safe loading limit. A future naval-architecture layer must calculate trim, heel, waterplane properties, righting arms, downflooding and damaged conditions.

The vessel mass ledger records component masses by subsystem and coordinates, computes tank fluid mass from volume, fill fraction and density, and returns category totals and first-moment centre of gravity. It is a bookkeeping baseline, not a stability solution. Tank free-surface effects, sloshing and changing liquid centroid remain future work.

The mass-budget hierarchy should be: (1) hull/crossbeam/foil structure; (2) rig and sails; (3) anchors and deck equipment; (4) propulsion and steering; (5) batteries, fuel and energy systems; (6) accommodation and appliances; (7) plumbing and tanks; (8) provisions, refrigeration, safety equipment and payload. Every mass item must have a reference position and a declared loading state. Empty, design-load and maximum-load cases should be tracked separately.

## Preliminary flow analysis

Independent aerodynamic and hydrodynamic plugins use the existing PhysicsSolver interface. Their first implementation calculates dynamic pressure, lift, drag, side force and Reynolds number from caller-supplied coefficients.

This is a low-order steady-flow screen, not CFD. It does not predict the coefficients and cannot prove that a sail or hydrofoil works.

Next flow-analysis layers:
1. Import and validate sail/foil polars and coefficient provenance.
2. Solve apparent-wind and sail-trim equilibrium.
3. Add hull resistance, hydrostatics and free-surface effects.
4. Model foil lift/drag, cavitation and ventilation.
5. Couple aerodynamic and hydrodynamic forces with six-degree-of-freedom vessel dynamics.
6. Transfer loads into structural FEM models.
7. Optimise a cruising catamaran subject to payload, accommodation, range, stability, strength and operating-envelope constraints.

The displacement-to-foil transition must be simulated as a transient problem, not inferred from a single steady-state lift calculation.

## Structural physics roadmap

The existing CalculiX T3D2 adapter is a one-element axial truss check, not a hull solver.

A hull-specific structural milestone requires structural thickness/material definitions, a controlled shell mesh, topology/normals/element quality checks, reviewed boundary conditions and loads, CalculiX shell analysis, reaction balance and mesh convergence, and results linked to the exact geometry revision.

## Security and reliability

- Do not execute arbitrary LLM-generated Python.
- Only whitelisted parameter edits may mutate hull geometry.
- Keep artifacts inside a configured project workspace.
- Run CAD and FEM tools in isolated workers with time and resource limits.
- Never treat a rendered model or low-order force screen as engineering validation.
- Require independent engineering review and physical testing for safety-critical use.

## Hull material as a design variable

Hull material is modelled as a build-up rather than a single material label. The screening interface accepts marine aluminium, glass-fibre composite, carbon-fibre composite, sandwich/honeycomb layers and reinforced concrete. Wood is excluded. Each layer's mass comes from cured laminate areal mass or explicit thickness and density. Secondary installation mass and supplier/project cost and maintenance inputs remain explicit; no hidden default values are used.

The result is a mass/cost/maintenance comparison only. It does not prove structural equivalence or calculate scantlings. Each alternative must be sized for the same load cases and separately reviewed for stiffness, strength, buckling, fatigue, impact, joints, local reinforcement, corrosion, galvanic isolation, fire and repairability. Concrete also requires cracking, reinforcement, shrinkage, creep and corrosion assessment.

## Universal engineering, manufacturing and invention support

The long-term architecture is defined in [UNIVERSAL_ENGINEERING_ROADMAP.md](UNIVERSAL_ENGINEERING_ROADMAP.md). It extends the core beyond yacht-specific calculations to general components and assemblies, materials and material condition, polymer and metal additive manufacturing, CNC machining, heat treatment, reverse engineering and TRIZ-based candidate generation. These are capability targets to be implemented incrementally through versioned contracts and isolated specialist workers, not claims about current solver coverage.

## Persistent project store and declarative extension registry

The additive `ProjectStore` persists append-only project snapshots, calculation records and artifact references in SQLite. Snapshot writes use expected-revision checks; calculation records preserve solver identity/version, input/result digests and pinned component revisions. A changed component revision marks dependent calculations and linked artifacts stale, including transitive dependencies declared in the snapshot. The store does not own large artifact bytes.

The additive `ExtensionRegistry` stores declarative capability manifests: API and semantic versions, operations, input/output schema IDs, units, coordinate frames, time scales, dependencies, licence, permissions, safety class, network/offline support and resource metadata. It checks metadata compatibility only. It does not load or execute plugin code. Existing dispatcher, pipeline, CAD and physics implementations remain unchanged. See [PROJECT_PERSISTENCE_AND_EXTENSION_REGISTRY.md](PROJECT_PERSISTENCE_AND_EXTENSION_REGISTRY.md).

## Universal task assembly and cross-domain coordination

The universal task orchestrator owns lifecycle, identity, context references, dependency scheduling, checkpoints, result validation and policy enforcement. It does not own discipline-specific scientific meaning. Specialist task handlers implement common lifecycle interfaces while retaining domain-specific schemas, models, assumptions and validation. The cross-domain coordinator composes those handlers into typed dependency graphs and propagates constraints and hazards across interfaces.

This is intentionally distinct from the existing engineering dispatcher: the dispatcher selects a concrete CAD/physics operation, while universal task assembly coordinates arbitrary task types and may invoke the engineering dispatcher as one specialist capability. It must reuse the existing WorkerRunner/TaskContext lifecycle rather than creating a parallel worker loop. The detailed target contract, context layers, goal graph, risk/autonomy model and incremental implementation plan are in [UNIVERSAL_TASK_ASSEMBLY_AND_BIOHYBRID_ENGINEERING.md](UNIVERSAL_TASK_ASSEMBLY_AND_BIOHYBRID_ENGINEERING.md).

## Biohybrid engineering and robot hygiene

Biohybrid engineering is a planned optional discipline pack connected to materials, mechanics, robotics, chemistry, electronics, manufacturing, reliability and biosafety. Its research scope includes bio-derived materials, exploratory living actuators, surface colonisation/anti-fouling, contamination monitoring and validated decontamination. These are research categories, not implemented capabilities.

Robots used around people or in contaminated environments require a fomite/carrier threat model covering external surfaces, tools, seams, internal cavities, ventilation/liquid paths, service access and transport between zones. Cleanability, inspectability, validated decontamination, replaceable sealed modules and service traceability are design requirements. Bacteriophages are bacteria-specific biological agents, not universal disinfectants. Biological approaches require qualified biosafety review, containment, exposure assessment and validated inactivation/waste handling; they must not replace established infection-control procedures. The Engineering Core architecture does not specify organism construction or biological operating protocols. See [UNIVERSAL_TASK_ASSEMBLY_AND_BIOHYBRID_ENGINEERING.md](UNIVERSAL_TASK_ASSEMBLY_AND_BIOHYBRID_ENGINEERING.md).
