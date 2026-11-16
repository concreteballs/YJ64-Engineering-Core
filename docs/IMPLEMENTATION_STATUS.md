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
| 3. External engineering ecosystem, adapters and coupled execution | Partially implemented | Existing CalculiX truss adapter; first typed-kernel-to-CalculiX axial-truss adapter; CAD adapters; candidate evaluation and adapter policy documented in EXTERNAL_ENGINEERING_ECOSYSTEM.md | General mesh/entity mapping, distributed and multi-member loads, isolated workers, additional solver pilots, coupling, reference benchmarks, compatibility and licence/version management |
| 4. Materials, manufacturing, reverse engineering and invention | Partially implemented | Hull material screening; material evidence records; visual-reference metadata and annotations; some CAD generation; artificial-muscle material discovery; separate chemistry and actuator discipline packs with versioned shared material-candidate/request contracts and validation tests | Persistent composition- and process-aware datasets; electrically/magnetically responsive composite models and experiments; metal casting; polymer/other-material moulding; material-specific forging (including titanium); heat-treatment and surface-engineering models; additive/CNC/joining; tolerances, inspection, scan reconstruction, repair/lifecycle and structured invention workflows. These are planned, not implemented solvers. |
| 5. Electrical power, electronics, instrumentation and communications | Planned | Requirements only | DC/AC networks, 12/24/48 V comparison, energy balance, batteries/BMS, generation/charging, cables/protection/faults, controls, sensors, navigation, communications and fail-safe behaviour |
| 6. Integrated marine application | Partially implemented | Parametric hull geometry/CAD; preliminary catamaran hydrostatics; mass budget; sail polar/apparent wind; coefficient-based aero/hydrodynamics; hull-material screening; hydrostatic panel pressure loads with polygon integration; ROV pressure-housing screen; prescribed six-DOF vessel point kinematics | Complete hull/global structure, stability/trim/damage, seakeeping, foils/rig/propulsion/propellers, electrical/electronics, accommodation/tanks/plumbing, integrated budgets and design validation |
| 7. Robotics, mechanisms and autonomous vehicles | Partially implemented | Vessel base-point six-DOF kinematics; modular biomechanical architecture; actuator-to-chemistry material request and candidate-response contracts with validation tests | Link/joint and multibody models, actuator-neutral interfaces, adjustable muscle mounts, active/passive spine models, contact/balance, manipulators, winches/hoists, ROV/AUV/UAV performance and local safety controllers |
| 8. Cross-domain application packs and open ecosystem | Planned | Physics domain catalogue and spaceflight target scope documented | Full aviation/space/industrial solvers, celestial mechanics/astrodynamics/cosmology, application packs, public module registry, contributor tooling and ecosystem integrations |
| 9. Human operational knowledge and emergency assistance | Planned | Requirements documented in the field-assistance architecture | Reviewed first-aid/medical guidance, chemistry and water safety, field materials/minerals, geography/ecology, woodworking, shelter/energy, emergency signalling, resource-aware field procedures and offline knowledge bundles |
| 10. Adaptive task assembly and offline deployment | Planned | Architectural requirements documented; no task-assembly runtime or on-device LLM deployment is claimed | Task/resource/environment modelling, module capability matching, workflow composition, hazard and evidence checks, local model/runtime packaging, signed offline data bundles, update/freshness controls and device capability profiling |

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

1. Package 1: initial coordinate-frame, geometry and typed load/boundary-condition foundations are implemented with tests. An additive SQLite ProjectStore and declarative ExtensionManifest/ExtensionRegistry now provide the first persistent snapshots, calculation/artifact provenance, stale-result propagation and capability compatibility checks. Remaining: richer schema migration policy, artifact content storage adapter, signed manifests/trust, runtime isolation, solver-specific typed adapters and mesh/entity mapping.
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


## Position, time and navigation integration status

**Planned — no general Position & Time Awareness service or Navigation Integration Hub is currently claimed as implemented.** The target includes multi-source location/time acquisition, last trusted fix, uncertainty-aware dead reckoning, phone/external sensor fusion, peer-device time assessment, UTC/timezone separation, source freshness and spoofing/jamming diagnostics. Routine marine navigation is to integrate existing products only through supported APIs/licensed interfaces and documented formats; no proprietary chart integration is assumed. Emergency Celestial Navigation is a separate optional offline module. See POSITION_TIME_AND_NAVIGATION_INTEGRATION.md.

## Celestial mechanics and cosmology status

**Planned — no celestial mechanics, astrodynamics or cosmology solver pack is currently claimed as implemented.** Candidate libraries and ephemeris sources require exact release, licence, reference-frame/time-scale and benchmark review. Multi-prover, symbolic and numerical workflows are architectural targets, not integrated capabilities. User hypotheses remain explicitly labelled research models until tested against independent calculations and observations. See CELESTIAL_MECHANICS_AND_COSMOLOGY.md.

## Field assistance and offline deployment status

**Planned — no medical, survival, field-chemistry or adaptive task-assembly module is currently claimed as implemented.** Operational content requires source traceability and domain review; medical/chemical workflows require additional safety review. Local LLM and solver deployment, offline bundles and update integrity are future capabilities. See FIELD_SURVIVAL_AND_EMERGENCY_ASSISTANCE.md and ADAPTIVE_TASK_ASSEMBLY_AND_OFFLINE_DEPLOYMENT.md.


## Package 1 — persistent projects and extension capability registry

**Implemented prototype — additive infrastructure, existing solver paths unchanged.** `src/yj64_engineering_core/persistence.py` provides a standard-library SQLite ProjectStore with append-only project snapshots, optimistic revision checks, canonical JSON/SHA-256 identity, calculation and artifact reference persistence, solver provenance, pinned component dependencies and stale propagation (including declared transitive component dependencies). Artifact bytes remain in caller-managed storage; SQLite stores references and metadata. `src/yj64_engineering_core/extensions.py` provides JSON-serializable extension manifests, semantic versions, API compatibility, declared dependencies and capability matching across schemas, units, coordinate frames and time scales. The registry is declarative only and does not load or execute plugin code.

Automated tests cover persistence across reopen, revision conflicts, digest validation, calculation/artifact provenance, stale propagation, manifest round trips, API mismatch, dependency checks and capability compatibility. CI must be observed before claiming the full workflow passes. Remaining work includes explicit schema migration tooling, external artifact-store adapters, signed manifests and trust policy, runtime sandbox/workers, capability negotiation with actual solver adapters, and mapping shared loads/frames onto solver mesh entities.


## Typed solver boundary and end-to-end integration probe

**Implemented prototype.** \`typed_solver.py\` adds a solver-neutral typed request/response protocol for existing \`Quantity\`, \`CoordinateFrameRegistry\`, \`AppliedLoad\` and \`BoundaryCondition\` objects. It rejects unknown frame references before solver execution, retains dimensions and source units, creates deterministic input digests from frame/load/condition/quantity data and component revision dependencies, and returns solver identity/version with the result. It does not map loads to FEM meshes or execute arbitrary plugins.

\`tests/test_typed_solver_integration.py\` exercises typed dispatch, mixed-unit SI normalization at the solver boundary, frame validation, SQLite calculation/artifact persistence and stale propagation after an upstream component revision changes. The reference solver is a deterministic software integration probe, not a physical solver. CI must be observed before this milestone is called passing.


## Typed CalculiX adapter — first external solver through the shared kernel

**Implemented prototype.** `src/yj64_engineering_core/physics/typed_calculix.py` connects the typed YJ64 request/response boundary to the existing CalculiX T3D2 axial-truss runner. It checks dimensions and converts the member length, area, elastic modulus and applied force to SI; transforms the force vector and application point into the world frame; verifies the axial direction and explicit root/tip target mapping; and preserves both adapter identity and the detected external CalculiX version.

The supported model is deliberately narrow: one straight prismatic axial member, one point force at its tip, and one fixed root. It is not a general CAD-to-mesh, distributed-load, multi-member, bending, buckling or solid-stress adapter. The existing CalculiX runner remains available unchanged. Automated adapter tests use a controlled solver double for boundary and mapping checks; the existing CI real-CalculiX test remains the external executable check. Numerical benchmark coverage and independent engineering validation remain separate follow-up work.


## CI correction note — typed CalculiX adapter

The first adapter CI attempt exposed a package-level circular import caused by eager re-export from `physics/__init__.py`. The adapter remains available through `yj64_engineering_core.TypedCalculiXAxialTrussSolver` and `yj64_engineering_core.physics.typed_calculix`; the eager physics-package re-export was removed. The corrected commit must pass the complete workflow before the adapter milestone is marked CI-verified.

## Chemistry & Molecular Design — first executable capability

**Implemented prototype — deterministic, evidence-aware screening.** `src/yj64_engineering_core/chemistry/screening.py` binds shared formulation contracts to shared `MaterialRecord` identities and explicit stimulus-response evidence. It screens supplied candidates against `ActuatorMaterialRequest` property limits and returns `candidate`, `rejected` or `unresolved` dispositions. Electric-field, magnetic-field and hybrid electric-plus-magnetic response are separate modes; hybrid requires both fields to be present in the same evidence record. SI field units are explicit (V/m, T and/or A/m). Missing, ambiguous or unit-mismatched property evidence remains unresolved; no implicit unit conversion or default material properties are invented.

`tests/test_chemistry_screening.py` covers successful screening, rejected limits, missing evidence, hybrid-mode separation, unit mismatch, hypothesis labelling and contract conversion. This is not a molecular generator, reaction predictor, synthesis planner, polymerization simulator or quantum/molecular-dynamics solver. No external scientific adapter is claimed integrated. See `CHEMISTRY_MODULE_IMPLEMENTATION.md`.

Next: add condition-aware evidence selection and shared-registry unit normalization, formulation authoring helpers, structure-file adapters and experiment-data intake before selecting scientific solver integrations.

**Cross-pack payload extension.** The shared MaterialCandidate contract now transports typed property evidence and electric/magnetic/hybrid stimulus-response evidence. Property records retain explicit evidence state, source, method, temperature and uncertainty. Chemistry screening converts its candidate records into this enriched response so the Artificial Muscle Engineering pack can consume actual evidence rather than only a material identifier.

## Cross-cutting Economic & Local Sourcing Module

**Implemented prototype:** `yj64_engineering_core.economics` defines destination/supplier locations, supplier offers, shipping quotes, BOM lines, assembly costs and a bounded economic comparison engine. It compares buying a finished item with assembling from supplied part offers, groups one shipping charge per supplier, estimates tax only for prices explicitly marked tax-exclusive, and ranks by total landed cost. Currency mismatches, unavailable stock and missing delivery quotes are not silently accepted. The first version uses caller-supplied commercial data; it does not discover suppliers or verify live prices.

**Implemented prototype:** `economics/discovery.py` provides map/GPS/manual destination contracts and category-specific local, domestic, international and China search planning. `index.html` is now deliberately user-only: the user selects only the delivery point and copies its coordinate context. The user does not set engineering or procurement criteria.


## Supplier catalog integration checkpoint

**Implemented prototype — read-only catalog adapter.** `src/yj64_engineering_core/economics/catalog.py` provides `MouserSearchAdapter` for the documented Mouser Search API keyword endpoint. It maps product identifiers, source URLs, price tiers, availability text, explicitly stated stock counts, minimum quantities and recognized lead-time units into `SupplierOffer` records. Currency symbols/locale formatting are checked; ambiguous dollar pricing is rejected. Supplier location, currency and tax-inclusion treatment are explicit caller inputs. The adapter does not create carts or place orders, and a separate destination shipping quote remains mandatory for a landed-cost ranking.

Automated tests use a fake transport and do not constitute a live API/account test. A deployment must inject the API key from a secret store; it must never be committed. Supplier search is planned from the user-selected destination, with separate local, domestic, worldwide and China market scopes. No city is hard-coded. See ECONOMIC_AND_LOCAL_SOURCING_MODULE.md.


## Global sourcing location and discovery planner

`economics/discovery.py` introduces `LocationSelection` with map, GPS and manual modes. GPS requires an explicit permission flag; map selection requires coordinates. `SupplierSearchPlanner` expands each selected product/material category into local-radius, domestic, international and China search tasks. The default category list distinguishes chemicals, polymers, metals, composites, electronics, mechanical parts, fasteners, actuators, sensors, cables, ceramics and manufacturing services. Tests validate consent rules and search-plan structure. The graphical map/GPS user interface and live supplier connectors are not yet implemented.


## Destination picker UI prototype

A root `index.html` now provides a mobile-friendly map/GPS destination picker. Map clicks select coordinates; GPS is requested only after an explicit button press. The page now lets the user select a map point or explicitly request GPS and copy only a versioned destination context. Categories, search terms, technical limits, quantities, budget, delivery deadline and market scopes are agent-authored. The map page does not collect location on load.


## Agent-authored sourcing interface

`economics/agent.py` defines `AgentSourcingRequest`, `TechnicalRequirement` and `plan_agent_request`. The engineering agent supplies categories/search terms, required quantity/unit, technical property bounds, budget/currency, delivery deadline, local radius and selected market scopes. The destination context comes from the user-selected map/GPS point; GPS requires explicit permission. The authenticated Vercel function `api/discovery.py` exposes `POST /api/discovery`, protected by `YJ64_AGENT_API_TOKEN`, and returns a validated category × market plan. The endpoint is planning-only: it does not run live supplier searches, persist a queue, verify prices/stock, or purchase. `docs/AGENT_SOURCING_API.md` contains the request contract. Tests cover agent control of parameters, budget currency, GPS consent, technical constraints and request parsing.


## 1688 marketplace connector checkpoint

`Nexscope1688SearchAdapter` is an optional read-only adapter for 1688 product search through Nexscope. It normalizes listing identity, supplier/shop identity, CNY price, MOQ and quantity-price tiers. It does not invent stock, delivery days, shipping, customs or freshness. The API documentation reports 10–19 credits per call; the adapter requires an API key and explicit `credit_budget_per_call >= 19`. No paid request has been executed. See `ECONOMIC_AND_LOCAL_SOURCING_MODULE.md`.
