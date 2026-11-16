# YJ64 Engineering Core — implementation status

This is the factual implementation ledger for UNIFIED_ENGINEERING_DEVELOPMENT_PLAN.md. A plan, candidate evaluation or catalogue entry is not an implemented solver.

## Status definitions

- Implemented prototype — executable code and automated tests exist; capability may be deliberately limited.
- Partially implemented — an executable foundation exists, but major parts of the intended capability remain.
- Planned — requirements are documented; no meaningful executable subsystem is present.
- Evaluating — an external candidate has been identified for review; no adoption or integration is implied.

## Consolidated work-package status

| Work package | Status | Existing implementation | Main remaining work |
|---|---|---|---|
| 1. Universal kernel, project model and extension contracts | Partially implemented | Request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass/CG/inertia, evidence/stale-result tracking; unit-aware quantities with SI/metric/US customary named units; built-in SI, metric engineering, European metric, US customary, UK imperial and marine-hybrid display profiles; per-field unit overrides; document unit-policy choices; explicit voice conversion intent parser; nominal pipe-size designation separated from physical dimensions; single-root coordinate-frame tree and rigid transforms; validated geometry primitives; typed force/moment loads and boundary conditions | Persistent project/artifact store, full provenance/version compatibility, plugin capability contracts, mesh/entity mapping, solver-specific load adapters, speech recognition/UI prompts, complete locale rendering, PDF/DOCX/OCR ingestion, translation/glossary services and persistent artifact storage |
| 2. Shared physics, materials, environments and evidence feedback | Partially implemented | Material identity/property evidence and in-memory registry; dry-air ideal-gas density; atmospheric-pressure seawater EOS-80; bounded marine/aero calculations | Persistent verified datasets, humid air, pressure-aware seawater, viscosity/conductivity, specialist media, experiment intake, discrepancy analysis, research-data collector and reviewed adaptive model updates |
| 3. External engineering ecosystem, adapters and coupled execution | Planned; candidate inventory defined | Existing limited CalculiX truss adapter and CAD adapters; candidate evaluation and adapter policy documented in EXTERNAL_ENGINEERING_ECOSYSTEM.md | Exact-release/licence/API reviews, adapter SDK, isolated workers, selected pilot integrations, coupling, benchmarks, compatibility and licence/version management |
| 4. Materials, manufacturing, reverse engineering and invention | Partially implemented | Hull material screening; material evidence records; visual-reference metadata and annotations; some CAD generation | Persistent composition- and process-aware datasets; metal casting; polymer/other-material moulding; material-specific forging (including titanium); heat-treatment and surface-engineering models; additive/CNC/joining; tolerances, inspection, scan reconstruction, repair/lifecycle and structured invention workflows. These are planned, not implemented solvers. |
| 5. Electrical power, electronics, instrumentation and communications | Planned | Requirements only | DC/AC networks, 12/24/48 V comparison, energy balance, batteries/BMS, generation/charging, cables/protection/faults, controls, sensors, navigation, communications and fail-safe behaviour |
| 6. Integrated marine application | Partially implemented | Parametric hull geometry/CAD; preliminary catamaran hydrostatics; mass budget; sail polar/apparent wind; coefficient-based aero/hydrodynamics; hull-material screening; hydrostatic panel pressure loads with polygon integration; ROV pressure-housing screen; prescribed six-DOF vessel point kinematics | Complete hull/global structure, stability/trim/damage, seakeeping, foils/rig/propulsion/propellers, electrical/electronics, accommodation/tanks/plumbing, integrated budgets and design validation |
| 7. Robotics, mechanisms and autonomous vehicles | Planned | Vessel base-point six-DOF kinematics is reusable groundwork; architecture requirements documented | Link/joint and multibody models, actuators, contact/balance on moving decks, manipulators, winches/hoists, ROV/AUV/UAV performance and local safety controllers |
| 8. Cross-domain application packs and open ecosystem | Planned | Physics domain catalogue and spaceflight target scope documented | Full aviation/space/industrial solvers, cryogenics/plasma where applicable, application packs, public module registry, contributor tooling and ecosystem integrations |

## Multilingual engineering workspace status

Architecture and acceptance requirements are documented in MULTILINGUAL_ENGINEERING_WORKSPACE.md and incorporated into the unified plan. Status: Partially implemented. The kernel now includes additional customary units, named SI/metric/US/marine display profiles, per-field overrides, document unit-policy values, voice-command intent parsing and a type that separates nominal pipe designations from physical dimensions. UI prompts, actual speech recognition, locale-aware rendering, PDF/DOCX/OCR extraction, translation providers, glossary management, protected-token integrity checks, review and translated export remain planned. A first UTF-8 Markdown/plain-text intake adapter is implemented with immutable source bytes, SHA-256 identity, language metadata and stable segment source spans.

## Package 4 scope clarification

Casting of metals, polymer injection/moulding and other applicable material-forming routes; forging of ferrous and non-ferrous alloys including titanium; and alloy-specific heat treatment are documented target capabilities. No general casting, polymer moulding, forging, titanium-forging or heat-treatment simulation engine is currently claimed as implemented. The user's observed forge demonstration is an illustrative example of material-dependent technique, not a proposed titanium production route. Such sequences are source-attributed observations until independently verified for a specified material and process.

Technical books and papers are planned as traceable reference sources. Their content must not be confused with validated executable models.

## Existing executable foundations

- Core: shared request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass properties, evidence and stale-result tracking.
- Physics kernel: evidence-aware material records and in-memory registry; dry-air ideal-gas density; atmospheric-pressure seawater density using UNESCO 1983 EOS-80.
- Quantities: Quantity, UnitDefinition, UnitRegistry and DEFAULT_UNIT_REGISTRY; explicit SI dimension vectors, named-unit conversion, offset temperature conversion, finite-value checks and extensible registration. Force, moment and pressure dimension constants are available.
- Coordinate frames: CoordinateFrame, CoordinateFrameRegistry and RigidTransform; a single-root right-handed frame tree, proper orthonormal rotations, point/vector mapping, inverse transforms and frame-to-frame composition.
- Geometry: frame-aware points/vectors, line segments, planes, axis-aligned bounding boxes, spheres and cylinders with finite-value, degeneracy and frame-consistency checks.
- Loads/conditions: AppliedLoad validates force/moment dimensions and application-point frames; BoundaryCondition validates fixed, displacement, rotation, pressure and temperature conditions. These are shared input contracts, not mesh-bound solver implementations. Tests have been added; do not claim CI success until a passing run is observed.
- Marine/aero: preliminary catamaran hydrostatics, mass budget, sail polar from supplied data, apparent wind, coefficient-based aero/hydrodynamics, hull material screening.
- Structures/ROV: axial member screening, limited CalculiX axial truss adapter, ROV cylindrical pressure-housing screen, hydrostatic panel pressure-load generation including polygon integration.
- Motion: six-DOF rigid-body point kinematics for a supplied/prescribed vessel state. This is not wave-response prediction, seakeeping, sensor fusion or robot stabilization.
- Geometry/visualization: parametric hull geometry, limited SVG/OpenSCAD/FreeCAD generation adapters, image metadata/hash intake and structured human annotations.

## Immediate implementation sequence

1. Package 1: initial coordinate-frame, geometry and typed load/boundary-condition foundations are implemented with tests. Next connect these shared types to existing solver interfaces and add persistent project/artifact provenance.
2. Package 3 evaluation: review exact releases, licences/dependencies, APIs and workflows for OpenMDAO, SALOME, FreeCAD, OpenModelica/OMSimulator, OpenFOAM, MOOSE, FEM candidates and relevant NASA tools. Evaluation does not mean adoption.
3. Package 3 pilots: after relevant YJ64 contracts stabilize, run small standalone benchmarks and implement the first thin, isolated adapter.
4. Package 2: expand material/environment evidence and reproducible experiment feedback.

## External-tool adoption record

The candidate shortlist and required review gates are maintained in EXTERNAL_ENGINEERING_ECOSYSTEM.md. No candidate is yet an accepted mandatory dependency. Record exact release, licence/dependency review, adapter version, benchmark, limitations and adoption decision before changing that status.

## Evidence and release policy

Automated tests verify software behaviour. Reference benchmarks verify numerical implementation. Experimental comparisons support physical validation. Independent engineering review, qualification and certification are separate levels. No prototype or screening result is a design approval or safe operating limit.

A model update retains old versions, exact provenance, test evidence and applicability limits. New experimental data never silently overwrites a released model.


## Latest verified CI checkpoint

Commit `69daf7b106e3b3d5e09796ee3c9f8b248a676740` (`fix: exclude source text from document metadata`) completed GitHub Actions run [43893156103](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/43893156103) with conclusion `success`. All workflow steps passed, including unit/FEM/CAD integration tests and the 12 m yacht-hull demonstration artifact generation. This verifies the repository state at that commit; it does not imply that planned subsystems are complete.

## Document intake prototype

The first source-document intake adapter is implemented and tested for UTF-8 Markdown/plain text. It retains immutable raw bytes, SHA-256 identity, language metadata and stable heading/paragraph/table/code segment spans. Extracted segment text is available as source content but is excluded from metadata serialization. PDF, DOCX, OCR, translation and reviewed export remain planned.

## Package 1 execution boundary

The following are implemented foundations and must not be recreated: unit/quantity registry and display profiles; explicit voice-unit intent parsing; nominal-size designation type; coordinate-frame tree and rigid transforms; validated geometry primitives; typed loads and boundary conditions. Their connection to solver-specific mesh/entity mappings, persistent project/artifact/provenance storage, plugin capability manifests and complete user-facing localization/voice/document workflows remains open.


## Mathematical notation and symbolic workspace status

**Planned — not yet integrated.** The target architecture is specified in MATHEMATICAL_NOTATION_AND_SYMBOLIC_WORKSPACE.md. LaTeX is selected as the primary human-readable mathematical notation. MathJax is the initial browser-rendering candidate; SymPy is the initial symbolic-computation candidate, both subject to exact-release, licence/dependency, API and benchmark review. The semantic expression contract, dimensional validation against the existing Quantity/unit registry, rendering adapter, parser and symbolic/numerical adapters are not yet implemented. Rendering, parsing, dimensional validity, mathematical correctness and physical validation must remain separate evidence states.


## Formal proof and theorem-prover ecosystem status

**Planned — no proof assistant or SAT/SMT adapter is currently claimed as integrated.** Lean 4 + Mathlib is the first pilot candidate. The target compatibility catalogue includes Rocq/Coq, Isabelle/HOL, Agda, Metamath, HOL Light, HOL4, PVS and ACL2, with Z3/cvc5 and similar automated reasoning tools treated separately. The prover-neutral proof-obligation/result contract, native artifact preservation, axiom/assumption audit, proof-certificate validation and adapter conformance tests remain unimplemented. A checked mathematical proof does not establish physical model validity or engineering qualification.
