# YJ64 Engineering Core — implementation status

This is the factual implementation ledger for UNIFIED_ENGINEERING_DEVELOPMENT_PLAN.md. A plan, candidate evaluation or catalogue entry is not an implemented solver.

**Programme navigation:** [STRATEGIC_MASTER_PLAN.md](STRATEGIC_MASTER_PLAN.md) contains the expandable strategic graph and stage-by-stage implementation checklists. [OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md](OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md) defines the cross-cutting monitoring/diagnostics foundation. [YJ64_MONITOR_REUSE_AND_INTEGRATION_PLAN.md](YJ64_MONITOR_REUSE_AND_INTEGRATION_PLAN.md) assesses the existing Android monitor prototype and its migration path. [AUTONOMOUS_ENGINEERING_CYCLE_AND_MASTER_ROADMAP.md](AUTONOMOUS_ENGINEERING_CYCLE_AND_MASTER_ROADMAP.md) contains the detailed execution plan for the shared autonomous cycle.

## Status definitions

- Implemented prototype — executable code and automated tests exist; capability may be deliberately limited.
- Partially implemented — an executable foundation exists, but major parts of the intended capability remain.
- Planned — requirements are documented; no meaningful executable subsystem is present.
- Evaluating — an external candidate has been identified for review; no adoption or integration is implied.

## Cross-cutting platform capability — Observability & Diagnostics

**Status: Partially implemented — common event-contract foundation and redaction tests added; shared collection remains planned.**

Verified implementation:
- `src/yj64_engineering_core/observability/events.py` defines versioned `yj64.diagnostic.v1` events with stable event identity, severity/outcome, service/component/environment, optional discipline/agent, trace/span/correlation/task IDs, repository/commit/workflow/deployment context, operation timing and typed error fields.
- Event construction validates required identifiers, schema version, timezone-aware timestamps, outcome/severity, SQLSTATE and HTTP status.
- Sensitive-key values, bearer credentials and URL user/password pairs are redacted before serialization.
- `tests/test_observability_events.py` covers event serialization, correlation, redaction and invalid inputs.
- `api/index.py` extracts validated PostgreSQL SQLSTATE from psycopg `.sqlstate` / `.pgcode`, classifies database failures into safe categories and avoids exposing raw exception text or credentials.

Not yet implemented:
- authenticated shared ingestion endpoint and durable telemetry store;
- bounded offline spool/forwarder for non-Android producers;
- end-to-end correlation propagation through CI, webhook, queue, worker, agents and solvers;
- standardized instrumentation across all modules;
- diagnostic bundles and immutable artifact references;
- metrics, distributed tracing runtime/exporters, alerting and operator drill-down;
- evidence-based diagnostic assistant and full fault-injection acceptance.

The separate [YJ64 monitor prototype](https://github.com/concreteballs/yj64-clean-bial2modFun5) is a source reference, not an integrated component. Its reusable concepts and code-level limitations are documented in [YJ64_MONITOR_REUSE_AND_INTEGRATION_PLAN.md](YJ64_MONITOR_REUSE_AND_INTEGRATION_PLAN.md). The live CI receiver's HTTP 503 remains unresolved; the current diagnostic category is not proof of root cause.

**Mandatory integration rule:** no engineering module is considered fully integrated until it emits the common diagnostic schema, propagates task/correlation identity, redacts sensitive data, and delivers diagnostic evidence to shared collection (or a bounded recoverable spool with visible delivery state). Local-only logs qualify only as prototype diagnostics.

Implementation specification: [OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md](OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md). This capability is mandatory for every discipline onboarding and for the autonomous-cycle acceptance test.

---

## Consolidated work-package status

| Work package | Status | Existing implementation | Main remaining work |
|---|---|---|---|
| 1. Universal kernel, project model and extension contracts | Partially implemented | Request/response contracts, solver interfaces, dispatcher, pipeline, component/dependency graph, mass/CG/inertia, evidence/stale-result tracking; unit-aware quantities with SI dimensions and named conversions; coordinate-frame tree, rigid transforms, validated geometry primitives; typed loads and boundary conditions | Persistent project/artifact store, full provenance/version compatibility, plugin capability contracts, mesh/entity mapping, solver-specific load adapters, speech/UI, document ingestion and persistent artifact storage |
| 2. Shared physics, materials, environments and evidence feedback | Partially implemented | Material identity/property evidence and in-memory registry; dry-air ideal-gas density; atmospheric-pressure seawater EOS-80; bounded marine/aero calculations | Persistent verified datasets, broader environmental models, experiment intake, discrepancy analysis and reviewed adaptive model updates |
| 3. External engineering ecosystem, adapters and coupled execution | Partially implemented | Existing CalculiX truss adapter; typed-kernel-to-CalculiX axial-truss adapter; CAD adapters; candidate evaluation and adapter policy documented | General mesh/entity mapping, distributed loads, isolated workers, additional solver pilots, coupling, benchmarks and compatibility/licence management |
| 4. Materials, manufacturing, reverse engineering and invention | Partially implemented | Hull material screening; material evidence records; visual-reference metadata; CAD generation; artificial-muscle material discovery; chemistry and actuator discipline packs with versioned material contracts | Persistent composition/process datasets; responsive composite models and experiments; manufacturing workflows, tolerances, inspection, scan reconstruction and lifecycle |
| 5. Electrical power, electronics, instrumentation and communications | Planned | Requirements only | DC/AC networks, batteries/BMS, generation/charging, wiring/protection, controls, sensors, communications and fail-safe behaviour |
| 6. Integrated marine application | Partially implemented | Parametric hull geometry/CAD; preliminary hydrostatics; mass budget; sail polar/apparent wind; bounded aero/hydrodynamics; hydrostatic panel loads; ROV pressure-housing screen; prescribed six-DOF vessel point kinematics | Complete hull/global structure, stability/damage, seakeeping, foils/rig/propulsion, electrical systems, accommodation/tanks/plumbing and integrated validation |
| 7. Robotics, mechanisms and autonomous vehicles | Partially implemented | Vessel base-point six-DOF kinematics; modular biomechanical architecture; actuator-to-chemistry material request and candidate-response contracts with validation tests | Link/joint and multibody models, actuator-neutral interfaces, muscle mounts, spine, contact/balance, manipulators, ROV/AUV/UAV performance and local safety controllers; planned human-motion learning, Spatial Motion Tokens and supervised full-performance proving-ground qualification |
| 8. Cross-domain application packs and open ecosystem | Planned | Physics domain catalogue and spaceflight target scope documented | Full aviation/space/industrial solvers, celestial mechanics/astrodynamics/cosmology, application packs, registry and ecosystem integrations |
| 9. Human operational knowledge and emergency assistance | Planned | Requirements documented | Reviewed first aid, chemistry/water safety, field materials, geography/ecology, woodworking, shelter/energy, emergency signalling and offline knowledge |
| 10. Adaptive task assembly and offline deployment | Planned | Architecture documented; no task-assembly runtime or on-device LLM deployment claimed | Task/resource/environment modelling, capability matching, workflow composition, local runtime packaging, signed offline bundles, update/rollback and device profiling |

## Multilingual engineering workspace status

Architecture and acceptance requirements are documented in MULTILINGUAL_ENGINEERING_WORKSPACE.md and incorporated into the unified plan. Status: Partially implemented. The kernel includes customary units, named SI/metric/US/marine display profiles, per-field overrides, document unit-policy values, voice-command intent parsing and a type separating nominal pipe designations from physical dimensions. UI prompts, actual speech recognition, locale-aware rendering, PDF/DOCX/OCR extraction, translation providers, glossary management, protected-token integrity checks, review and translated export remain planned. A first UTF-8 Markdown/plain-text intake adapter is implemented with immutable source bytes, SHA-256 identity, language metadata and stable segment source spans.
