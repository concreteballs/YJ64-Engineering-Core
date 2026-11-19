> [!IMPORTANT]
> ## Repository boundary — autonomous cycle moved to Motocicl
> The autonomous Council/cycle runtime, durable orchestration, provider execution, CI self-repair and cycle-owned infrastructure are being separated into **[concreteballs/Motocicl](https://github.com/concreteballs/Motocicl)**.
>
> **This Engineering Core repository is no longer the place to implement or extend the autonomous cycle itself.** Do not add a second queue, scheduler, general-purpose worker, model-provider runtime, cycle controller or browser-agent transport here.
>
> Engineering Core remains responsible for domain engineering, specialist solvers, engineering task handlers, evidence/validation within engineering disciplines, and its narrow adapter to the external Council/cycle API.
>
> The existing cycle plan below is deliberately preserved as historical/source material. Its cycle-related implementation work is now assigned to Motocicl. Use the extraction inventory and authoritative execution plan in [Motocicl — Repository Split Plan](https://github.com/concreteballs/Motocicl/blob/main/REPOSITORY_SPLIT_PLAN.md). Do not execute cycle tasks from this file in this repository. Only Engineering Core-specific work and the integration contract between the two repositories remain actionable here.
>
> **Migration status:** plan and repository boundary notice only. Source files have not yet been moved. The next migration step must follow the file-by-file inventory in Motocicl and preserve working interfaces/tests.

---

# YJ64 Engineering Core — Autonomous Cycle and Master Roadmap

Last reconciled: 2026-11-17
Repository: concreteballs/YJ64-Engineering-Core
Authorized branch: main

This document is the execution index for the autonomous development cycle. It separates verified implementation from planned work. The detailed subsystem ledger remains in IMPLEMENTATION_STATUS.md; this file records the current control-loop priority and the order in which the remaining master plan should be executed. The mandatory [Session Independence Protocol](SESSION_INDEPENDENCE_PROTOCOL.md) defines how task state survives model-context rollover, worker restart and the end of any user-facing chat.

**Strategic programme index:** see [STRATEGIC_MASTER_PLAN.md](STRATEGIC_MASTER_PLAN.md) for the expandable strategic graph and the implementation checklists beneath each major stage. This document remains the detailed autonomous-cycle execution plan.

## 1. Verified completed work

"Completed" means the stated prototype/code and automated tests exist. It does not imply production qualification, complete domain coverage, or integration of external solvers unless explicitly stated.

### Core engineering foundations — implemented prototypes
- Shared engineering contracts, dispatcher and pipeline.
- Component/dependency model, mass properties and stale-result tracking.
- Quantity/unit registry, SI dimensions, named unit conversions and display profiles.
- Coordinate-frame tree, rigid transforms, validated geometry primitives.
- Typed loads and boundary-condition contracts.
- Additive SQLite project snapshots, calculation/artifact references, provenance metadata and stale propagation.
- Declarative extension manifests and capability matching.
- Typed solver request/response boundary and deterministic integration probe.
- Narrow typed CalculiX axial-truss adapter (one straight prismatic axial member, tip point force, fixed root); not a general FEM adapter.
- Source-document intake prototype for UTF-8 Markdown/plain text with immutable source identity, hash, language and stable segment spans.

### Chemistry and artificial muscles — implemented prototypes
- Chemistry & Molecular Design screening foundation.
- Artificial Muscle Engineering discipline pack.
- Versioned shared chemistry/actuator material contracts.
- Evidence-aware candidate screening for electric, magnetic and hybrid response modes.
- Tests for contract validation, evidence states and cross-pack candidate exchange.
- No molecular generator, synthesis predictor, quantum chemistry or molecular dynamics solver is claimed integrated.

### Economics and sourcing — implemented prototypes
- BOM, supplier offer, shipping quote, assembly cost and landed-cost comparison contracts/engine.
- Agent-authored sourcing requests and technical requirements.
- Destination-only user input model: user selects delivery point; engineering agent authors categories, terms, quantities, technical limits, budget, deadline, radius and market scopes.
- Mobile map/GPS destination picker; GPS is explicit-consent only.
- Authenticated planning endpoint POST /api/discovery, protected by YJ64_AGENT_API_TOKEN.
- Mouser read-only catalogue adapter foundation.
- Optional 1688/Nexscope read-only adapter with explicit API key and credit-budget guard.
- Bounded provider executor with external-call and credit caps; currently only China/1688 is executable when explicitly registered. Other scopes report missing providers.
- Tests cover sourcing calculations, planning, catalogue normalization and bounded execution.

### CI and autonomous-cycle foundation — implemented prototypes, deployment pending
- GitHub Actions Python/FEM/CAD test workflow.
- GitHub Actions completion-webhook sender for pushes to main.
- Authenticated Vercel CI receiver with repository/branch/workflow/event validation.
- PostgreSQL migration for durable CI event records and task queue.
- PostgreSQL store with idempotent CI event persistence, one processing task per event, atomic leased claims, bounded retries, completion and blocked states.
- Vercel receiver now persists accepted events and enqueues a process_ci_event task when PostgreSQL is configured; it does not run a model or repository code.
- Tests for event persistence, duplicate suppression, lease claiming, completion, retry and ingress validation.
- Latest verified Python test run: [44097061043](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/44097061043), conclusion success, commit 3a390ae44f5b16dc197f740403ef64c38f6d5118.
- The separate CI completion-webhook delivery run [44098093733](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/44098093733) failed with HTTP 503 (persistent_queue_unavailable); URL canonicalization and webhook authentication had already passed, so the previous 401/secret-alignment note is obsolete.
- Supabase project ggambesixwejgbjwtnhw is active; migrations 0001 and 0002 are applied; both public.yj64_ci_events and public.yj64_task_queue exist with expected columns. The Vercel Production YJ64_DATABASE_URL is configured. Direct Supabase checks confirmed public search_path resolution, INSERT privileges for postgres, and RLS bypass for that role. These checks do not prove that Vercel's live runtime connection can execute the transaction.
- Actual end-to-end event and task persistence remain unverified because the receiver still returns 503. The receiver now extracts validated SQLSTATE from psycopg .sqlstate or .pgcode before falling back to exception-class mapping, and exposes only a safe diagnostic category. The live 503 remains unresolved; inspect the actual current SQLSTATE/category and correlate it with deployment/run evidence rather than assuming the category alone identifies root cause.
- The cloud worker and autonomous continuation are not implemented. Session-independent orchestration is a required design gate, not an existing capability. Passing Python tests do not mean the autonomous cloud loop is operational.

## 2. Current priority: finish the autonomous engineering cycle

Cross-cutting prerequisite: implement the observability and diagnostic foundation defined in [OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md](OBSERVABILITY_AND_DIAGNOSTICS_ARCHITECTURE.md), using the assessed [YJ64 monitor prototype](YJ64_MONITOR_REUSE_AND_INTEGRATION_PLAN.md) as a source for portable event and offline-delivery patterns. The common event schema and initial redaction tests now exist; shared ingestion, durable telemetry storage and end-to-end propagation remain outstanding. **No engineering module is fully integrated until it emits the common diagnostic contract and delivers evidence to shared collection or a bounded recoverable spool with visible delivery state.** The current HTTP 503 investigation is an immediate use case: preserve exact safe SQLSTATE/category, deployment identity, correlation IDs and the failing operation before selecting a fix.

Do not start broad implementation of every engineering discipline until this cycle is operational. The cycle must be capable of taking the next incomplete task from this roadmap, executing bounded work, validating it, recording the result and continuing without requiring the user's phone to remain online. It must also be independent of any ChatGPT UI conversation or context-window lifetime; see [SESSION_INDEPENDENCE_PROTOCOL.md](SESSION_INDEPENDENCE_PROTOCOL.md).

### Cycle milestone A — reliable event delivery

Implemented in code:
- GitHub Actions completion-event sender.
- Authenticated receiver with strict repository, branch, workflow, event, run identity, commit and URL validation.
- Idempotent persistence design and duplicate protection.

Still required:
- Authentication and canonical URL checks have passed in the latest diagnostic sequence; do not repeat secret rotation without new evidence.
- Verify the currently deployed Vercel version and preserve the successful authentication evidence.
- Resolve the PostgreSQL 503 using precise SQLSTATE diagnostics; then verify the receiver returns HTTP 202.
- Record and verify successful end-to-end delivery and actual event/task rows; do not treat configured secrets or table existence as proof of delivery.

### Cycle milestone B — durable task state

Implemented in code:
- PostgreSQL schema migration for CI events and task queue.
- Persistent event store and idempotent process_ci_event enqueue.
- Atomic queue claim with FOR UPDATE SKIP LOCKED and expiring worker lease.
- Bounded retry, completion and blocked-state operations.
- Automated tests using a controlled database double.

Still required:
- Production Supabase PostgreSQL project exists and migrations 0001/0002 are applied; Vercel Production YJ64_DATABASE_URL is configured.
- Resolve the live receiver's HTTP 503. Its current database_schema_error diagnostic is not conclusive: inspect .sqlstate and .pgcode before generic exception names, then retain only validated SQLSTATE/category in safe diagnostics.
- Verify real persistence, deduplication, queue claims and restart recovery against the live database.
- Add task history, dependency/parent linkage, artifacts/log references and backup/retention policy as the worker contract matures.

### Model-provider limits and input transport — mandatory part of milestones C/D
- Implement [MODEL_PROVIDER_LIMITS_AND_CHUNKED_INGESTION.md](MODEL_PROVIDER_LIMITS_AND_CHUNKED_INGESTION.md): provider-specific context, RPM, TPM, concurrency, payload and quota awareness.
- Detect/classify 429, Retry-After/reset headers, 413/context overflow, transient failures and permanent auth/billing/configuration errors; persist retry scheduling and release workers instead of sleeping or silently storing errors.
- Split oversized inputs into ordered, hashed, idempotently acknowledged chunks. Use explicit accumulation/FINALIZE semantics only where endpoint continuity is guaranteed; otherwise reassemble from durable storage before sending a complete fitting request.
- Do not begin model work until the complete payload manifest and total hash have been verified. Add the provider-limit and chunk-integrity acceptance tests before autonomous qualification.

### Cycle milestone C — cloud worker and authorized agent
- Deploy a separate cloud worker that can wake from queued work independently of the user's device.
- Implement the [Session Independence Protocol](SESSION_INDEPENDENCE_PROTOCOL.md): durable task/checkpoint state, replaceable model-call sessions, context-budget monitoring, automatic checkpoint-and-continue, and recovery after process/model-call interruption.
- Each model request receives only the task-scoped context it needs, reconstructed from durable state, verified artifacts and a compact checkpoint; it must not depend on reading the previous ChatGPT conversation.
- A context rollover creates a new model API request/session automatically. It is not a request for the user to press the ChatGPT “New chat” button.
- Give it access only to this repository and the authorized main workflow; do not grant unrelated repositories.
- Connect an explicitly configured model provider through server-side secrets. No model API key is assumed to exist.
- Worker reads this roadmap and implementation ledger, chooses the next unblocked task, prepares a bounded change, runs local checks and submits the change to the authorized branch.
- Preserve a complete task/decision/provenance record.
- Do not claim this worker can resume the exact ChatGPT conversation. A supported notification bridge is a separate integration.

### Cycle milestone D — validation and closed-loop continuation
- On every change, wait for the exact GitHub Actions run associated with its commit.
- Before a context budget is exhausted, persist a versioned checkpoint containing current task state, completed actions, pending actions, decisions with evidence references, artifact/commit IDs, retry counters, budget consumption and next safe action.
- Start the next model request from that checkpoint and authoritative task records; retain a link to prior model-call IDs only for audit, never as the sole source of state.
- Recover expired worker leases and interrupted model calls through idempotency keys and explicit uncertain-outcome reconciliation; do not blindly repeat side effects.
- On success, record commit, run URL, conclusion and test evidence, then mark the task complete and select the next task.
- On failure, collect job summaries and logs, classify the cause, and permit only bounded repair attempts.
- Re-run CI after every repair.
- Stop and mark blocked on ambiguous requirements, repeated failure, unavailable credentials, unexpected permission needs, destructive changes, paid external calls, purchases, physical actuation or safety-critical decisions.
- Never mark a task complete based only on code generation or a started workflow.
- Enforce maximum tasks per cycle, maximum repair attempts, time/cost/token budgets and an explicit kill switch.

### Cycle milestone E — notifications and operator control
- Deliver completion, failure, blocked and approval-required notifications to a configured external channel.
- Provide a status view showing active task, queue, last successful commit, last CI result, next task, budget consumption and stop reason.
- Provide pause/resume/cancel controls with authenticated operator actions.
- Keep the user in control of external purchases, paid API credits, data sharing, deployment secrets and consequential physical operations.

### Cycle acceptance test

The autonomous cycle is operational only after a test demonstrates the full sequence:
1. A task is enqueued durably.
2. A cloud worker claims it after the user's phone is offline.
3. The worker makes a small authorized repository change.
4. GitHub Actions runs for that exact commit.
5. A verified completion event reaches the receiver and is deduplicated.
6. The worker records the CI result and advances to the next eligible task, or stops with an explicit reason.
7. Restarting the worker does not lose or duplicate the task.
8. A forced context-window rollover completes the same task across at least two distinct model-call sessions without manual intervention or loss of evidence.
9. A worker crash after checkpoint and before/after a model response resumes safely; duplicate delivery is idempotently suppressed or reconciled.
10. Pause/kill switch and budget limits are demonstrated.

Until all acceptance criteria pass, describe the system as partially implemented, not autonomous.

## Cross-program architecture plans (approved additions; staged, not implemented)

The autonomous cycle will also provide the bounded implementation/validation bridge for the following approved plans. These do not replace the cycle milestones or authorize parallel duplicate engines:

- [Consensus, Decision Integrity and Evidence-Based Engineering](CONSENSUS_DECISION_INTEGRITY_AND_EVIDENCE_PLAN.md): reusable consensus/critique, independent secret voting, private domain competence estimates, evidence-integrity checks and validation feedback. Round supervision/repetition control remains in the application.
- [Browser-Agent Feedback Bridge](BROWSER_AGENT_FEEDBACK_BRIDGE_PLAN.md): external browser observer reports exact CI/test evidence to the durable cycle; the engineering worker cross-checks and continues or stops. It is a transport/observer bridge, not another consensus or rating subsystem.
- [Versioned Browser-Agent Envelope](../schemas/browser-agent-envelope.schema.json): initial machine-readable message envelope contract. It is a schema foundation only; no live bridge or browser-agent integration is claimed.

## 2A. Approved ChatGPT ↔ Cycle ↔ Browser-Agent communication architecture

The detailed contract is [ChatGPT Cycle Browser-Agent Channel](CHATGPT_CYCLE_BROWSER_AGENT_CHANNEL.md); the external CI observer contract remains [Browser-Agent Feedback Bridge](BROWSER_AGENT_FEEDBACK_BRIDGE_PLAN.md). The existing [versioned envelope schema](../schemas/browser-agent-envelope.schema.json) and `automation/browser_agent_bridge.py` validator are foundations only. No live ChatGPT-to-cycle or browser-agent delivery is claimed.

Two routes are required:

1. **Direct route:** ChatGPT writes an immutable request; the cycle validates and acknowledges it, executes bounded work, persists a response; the application-level Agent Communication Hub routes the response through a configured browser-agent provider back to the shared chat.
2. **Council route:** for high uncertainty, cross-discipline or safety-critical questions, the cycle first submits scoped claims and evidence to the existing council; it preserves disagreement/minority views and then returns the structured result through the same Hub/browser-agent delivery path. Routine tasks do not invoke the council.

The GitHub bootstrap exchange uses immutable one-message-per-file records under `agent-bridge/requests/`, `receipts/`, `responses/`, `agent-reports/` and `council/`. Never use one mutable inbox/outbox file. Reuse the existing Postgres task queue and artifact store for authoritative scheduling, leases, deduplication and large payloads; do not create a parallel queue or duplicate consensus subsystem. GitHub files are a traceable exchange format, not a substitute for atomic queue operations. No secrets or unrestricted personal data may be committed.

The Agent Communication Hub belongs to the application layer, not the Engineering Core worker. It must expose a provider-neutral adapter registry, user-controlled enable/disable and priority, health/availability, capability scopes, acknowledgements, bounded retries and failover. Users may add providers through supported MCP/API/extension/desktop adapters without changing the cycle protocol. Initial candidates: Perplexity Comet (cross-platform candidate), Opera Neon MCP Connector (integration candidate), Claude in Chrome (desktop-only), Gemini in Chrome and Microsoft Edge Copilot. These are candidates, not assumed integrations: validate actual connectivity and capabilities before enabling. At least two providers must be addable without changing cycle code.

Never expose private council deliberations, hidden model ratings or secret votes to browser providers. Browser content and agent output are untrusted. Consequential browser actions require explicit human approval. Agent assertions cannot alone mark a task complete; the cycle cross-checks GitHub/CI and task evidence. If all providers are offline, retain the response durably as delivery-pending.

### Prioritized implementation blocks — fastest safe path to a working cycle

Execute in this order; keep each block small and acceptance-tested:

**Block 0 — restore a verified live foundation (immediate gate).**
- Recheck current deployed receiver and current HTTP/database diagnostic; do not rely on stale roadmap status or old run IDs.
- Resolve the live PostgreSQL 503 from validated SQLSTATE and deployment evidence; verify a real HTTP 202 and corresponding event/task rows.
- Verify live queue claim, lease expiry/recovery, idempotent enqueue and artifact persistence against Supabase. Passing mocked unit tests is insufficient.
- Do not start model execution while live persistence is unverified.

**Block 1 — one durable message path, without browser vendors.**
- Map and reuse existing task queue, checkpoints and artifact store.
- Add request/receipt/response records, correlation/parent IDs, immutable message identity, idempotency, expiry, payload hash and delivery state using existing persistence primitives.
- A GitHub request file may bootstrap ingress, but the worker must ingest it into the durable queue; response payloads/artifacts must be persisted before acknowledgement.
- Prove ChatGPT-style request → durable receipt → stored response using a test harness. Do not build a new queue.

**Block 2 — make one real model call.**
- Implement/configure one provider adapter only after explicit credentials, verified provider profile and global/task budgets exist.
- Invoke existing admission/reservation, provider-limit, chunk-integrity and ambiguous-outcome reconciliation paths from the scheduler.
- Persist the full response as a durable artifact before settling the reservation or completing the task.
- Prove one bounded task from queue claim through model request, persisted result and safe retry/recovery. No credentials or prompts in logs/GitHub files.

**Block 3 — authorized task executor and CI closure.**
- Register a narrowly scoped handler that reads the roadmap/implementation ledger, selects one unblocked task and produces a small authorized patch.
- Run checks and commit only within the repository/main scope; associate the exact commit with its GitHub Actions run.
- Consume the verified CI completion event; classify success/failure; permit bounded repair only when evidence changes; otherwise block with an explicit reason.
- Never mark completion from generated code or a started CI run.

**Block 4 — autonomous continuation and session independence.**
- Connect checkpoint persistence, context-budget rollover, worker restart recovery, uncertain-call reconciliation and idempotent continuation.
- Enforce task/repair/time/token/cost ceilings, approval gates, pause/cancel and kill switch.
- Demonstrate phone/UI disconnection, worker restart and forced model-context rollover without losing state.

**Block 5 — browser-agent delivery and council escalation.**
- Implement the application-level Agent Communication Hub and provider registry, separate from the cycle worker.
- Add one verified provider adapter and deliver a cycle response into the shared chat; preserve pending delivery if unavailable.
- Add council escalation through the existing consensus subsystem, preserving dissent and evidence.
- Add further providers and failover only after the first route works.

**Block 6 — operator controls and full acceptance.**
- Status view, notifications, pause/resume/cancel and provider management.
- End-to-end acceptance: durable request → cycle execution → exact-commit CI verification → response persisted → browser-agent delivery; plus a separate council-first case, duplicate/stale/spoofed message rejection, provider outage recovery and kill-switch test.

**Critical-path rule:** Blocks 0–4 make the autonomous cycle execute and verify work. Block 5 completes the requested browser-agent communication architecture, but browser vendor integrations must not delay the first functioning execution loop. Blocks 0–2 are the immediate focus; start Block 0 with a live database/queue verification and then move directly to the first failing gate.

## 3. Master engineering roadmap after the cycle is operational

The worker must use docs/IMPLEMENTATION_STATUS.md as the detailed source of truth, avoid recreating completed foundations, and execute the remaining work in dependency order:

1. **Core kernel completion:** schema migrations, external artifact storage, signed extension manifests/trust policy, runtime isolation, capability negotiation, mesh/entity mapping and solver-specific load adapters.
2. **Shared physics and evidence:** persistent verified datasets, broader environmental/material models, experiment intake, discrepancy analysis and reviewed adaptive model updates.
3. **External solver ecosystem:** exact-release/licence/API review, isolated pilot adapters, reference benchmarks, coupled execution and version/compatibility management. Candidate tools are not integrations until tested and recorded.
4. **Chemistry and responsive materials:** condition-aware evidence selection, formulation authoring, structure-file intake, experiment-data workflows, and carefully benchmarked scientific solver adapters for electrically/magnetically responsive composites.
5. **Manufacturing and reverse engineering:** material/process datasets and validated workflows for casting, polymer moulding, forging, heat treatment, additive/CNC, joining, tolerances, inspection, scan reconstruction, repair and lifecycle.
6. **Electrical/electronics/instrumentation:** power networks, batteries/BMS, charging/generation, wiring/protection, controls, sensors, communications and fail-safe behaviour.
7. **Integrated marine engineering:** hull/global structure, stability, damage, seakeeping, foils, rig, propulsion, electrical systems, accommodation, tanks/plumbing and integrated verification.
8. **Robotics and autonomous vehicles:** multibody/link/joint models, actuator-neutral interfaces, artificial muscle mounts, spine, contact/balance, manipulators, winches, ROV/AUV/UAV and local safety controllers.
9. **Cross-domain packs:** aviation, spaceflight, industrial systems, celestial mechanics, astrodynamics and cosmology, with independent validation and evidence labels.
10. **Human operational knowledge:** traceable and reviewed field assistance, first aid, chemistry/water safety, materials, shelter, energy, communications and offline knowledge.
11. **Adaptive task assembly and offline deployment:** capability matching, workflow composition, local model/runtime packaging, signed field bundles, freshness/rollback and device profiling.
12. **Mathematical/proof/navigation ecosystems:** symbolic workspace, LaTeX rendering/parsing, dimensional checks, proof-obligation and prover adapters, position/time awareness, navigation integration and optional celestial navigation.
13. **Multi-model and physical validation:** model disagreement handling, independent deterministic/physical validators, prediction-versus-observation records, confidence calibration and experiment feedback.

Every roadmap item must be broken into small tasks with prerequisites, acceptance tests, evidence level, resource estimate, cost ceiling and stop conditions before execution.

## 4. Global execution rules

- Repository scope: concreteballs/YJ64-Engineering-Core only.
- Branch: main only.
- Preserve existing interfaces unless a tested migration is supplied.
- No secrets in source, commits, logs or chat.
- No paid API requests without explicit per-call budget and configured credentials.
- No purchases, external account changes, physical actuation or hazardous operations without explicit approval.
- Do not fabricate supplier prices, stock, shipping, solver results, test outcomes or evidence.
- Separate hypothesis, candidate, deterministic calculation, simulation, benchmark, experiment and independent review.
- Prefer additive, reversible changes and small commits.
- Every completed task must link its code commit, tests, CI run and limitations.
- Every module onboarding must pass the mandatory Observability & Diagnostics integration gate; local-only logs are prototype-level diagnostics, not full integration.
- Update this roadmap and IMPLEMENTATION_STATUS.md as part of the same task that changes implementation status.


## 5. Robotics learning, motion skills and high-dynamic qualification

**Status: planned architecture; no visual imitation-learning runtime, motion-token store, humanoid whole-body controller or high-dynamic proving ground is claimed implemented.** This work is to be added after the autonomous cycle foundation is operational and alongside the robotics discipline pack.

### 5.1 Human Motion Learning & Adaptive Skill Acquisition

A dedicated cross-cutting discipline learns from human demonstrations and observation, then transfers validated skills to the robot's own morphology:
- Visual perception extracts body pose, joint/segment trajectories, timing, contacts, object interactions and uncertainty. Raw video is not the skill representation.
- Motion retargeting maps human movement to the robot's own links, joints, actuator limits, mass properties and coordinate frames; it must not assume human/robot proportions or degrees of freedom are identical.
- Imitation learning builds an initial candidate skill from demonstration; iterative practice compares observed robot motion with the target and updates parameters.
- Skill abstraction extracts reusable principles (weight transfer, balance recovery, sequencing, momentum transfer, braking and contact strategy) rather than storing only a named routine such as boxing or walking.
- Skill transfer is conditional: a learned principle may be reused in another task only after checking morphology, contact, environment, loads, uncertainty and safety envelope.
- Observational learning from public environments should default to on-device/ephemeral perception and retain generalized, non-identifying motion features rather than raw video or identity. Retention, consent, privacy and deletion policy must be explicit.

### 5.2 Spatial Motion Token (SMT) — compact executable skill representation

Create a versioned **Spatial Motion Token** format, not an LLM word token and not a raw video clip. An SMT is a compact, indexed, machine-readable motion primitive that can be retrieved and dispatched quickly by the perception/control stack without asking a language model to re-derive the movement.

Each token should include:
- stable skill ID, version, content hash, provenance and evidence/validation level;
- semantic intent and task context (e.g. step, pivot, evade, recover balance, carry object);
- robot morphology/kinematic profile and coordinate-frame references;
- phase sequence, time parameters, joint/segment trajectories and allowable variation;
- centre-of-mass path, support/contact sequence, momentum/torque/energy envelope and actuator demand;
- required objects/surfaces, free-space/collision constraints and environmental preconditions;
- force, speed, acceleration, thermal and duty-cycle limits plus abort/recovery behaviour;
- confidence, known failure modes, tested envelope, compatible robot configurations and links to simulation/experiment evidence.

SMTs should support parameterized primitives and composition into longer skills. Runtime retrieval uses perception/context matching; a deterministic low-level controller executes the selected primitive with live feedback. Tokens are not blindly replayed: preconditions, collision checks, stability and current actuator health must be verified first. Fast execution must not depend on live LLM inference.

### 5.3 Progressive training and full-performance proving ground

Training must not stop at permanently reduced speed or force. The qualification plan must progress from low-energy supervised trials through intermediate envelopes to the robot's specified full operating envelope for the maneuver, including full rated speed/force where the hardware and test fixture are qualified.

The final high-performance stage is a deliberate test mode, not an unrestricted everyday mode:
- a human supervisor observes, gives demonstrations/corrections and can pause or abort immediately; the supervisor remains outside the robot's motion/impact envelope or behind a suitable barrier;
- a purpose-built proving ground uses impact-absorbing floor mats, inflatable/energy-absorbing obstacles, protected boundaries, controlled clearances, and replaceable sacrificial fixtures; mats/inflatables alone are not assumed sufficient for a heavy/high-energy robot;
- use appropriate restraint/tether/overhead support, remote emergency stop, independent power isolation, safety-rated speed/force limits where needed, exclusion zones, protective barriers and instrumented load/temperature/position monitoring;
- progress through documented test gates. Full-performance trials are permitted only for a specific maneuver after its structure, actuators, thermal limits, stopping distance, fixture and recovery behaviour have been assessed;
- do not remove emergency stops, containment, interlocks or human-exclusion protections to create a no-limits test. The aim is to reach full rated maneuver performance inside a qualified, controlled test envelope, not to exceed design limits or expose people to impact;
- retain each trial's conditions, sensor traces, token version, supervisor feedback, result and any updated limits. A failed or out-of-envelope trial returns the skill to review.

### 5.4 Training and transfer sequence

1. Human demonstration and perception/pose extraction.
2. Candidate SMT generation and morphology-aware retargeting.
3. Physics checks and simulation with explicit uncertainty/evidence labels.
4. Low-energy supervised physical rehearsal with fall/impact protection.
5. Incremental envelope expansion with measured acceptance criteria.
6. Supervised full-rated performance trials in the qualified proving ground.
7. Store a validated SMT version and publish reusable subskills to the shared skill library.
8. Permit transfer to another task only after context and safety-envelope checks.

### 5.5 Integration points

- Dynamic Maneuvering & Momentum Management: centre-of-mass, angular momentum, whole-body dynamics and reusable movement primitives.
- Artificial Muscle Engineering: actuator force/velocity/thermal/duty-cycle envelopes and damage indicators.
- Robot Geometry and shared physics: morphology, mass/inertia, joint limits, contact and collision geometry.
- Control Systems: real-time feedback, balance, contact and deterministic execution.
- Safety & Environment Interaction: people/object separation, force limits, stop/recovery and test-zone interlocks.
- Shared Autonomous Engineering Cycle: queues simulation/training jobs, stores artifacts, records provenance and triggers next stages; it is the common orchestration layer, not a separate loop embedded in the learning module.

## 4.1 Initial durable checkpoint implementation status

**Implemented and CI-verified:** a canonical, hash-verified task checkpoint contract and PostgreSQL append-only persistence methods. Checkpoints preserve task state, budget and approval snapshots, artifact references, sequence numbers and previous-checkpoint linkage. Repeated writes of the same checkpoint are idempotent; conflicting content for an existing sequence is rejected. Latest-checkpoint recovery verifies the stored integrity hash before returning state.

**Database:** the `yj64_task_checkpoints` table is deployed to the YJ64 Supabase project with RLS enabled and server-role-only access. It is empty pending application-level integration. No autonomous worker is running; queue claim/lease, checkpoint save/recovery, provider calls and durable retry scheduling have not yet been proven end to end.

**Next implementation gates:** (1) verify actual database round-trip with a disposable queued task and remove the test data; (2) bind checkpoint save/recovery to task lifecycle and lease ownership; (3) add provider request metadata and durable retry schedule; (4) implement and test provider-limit classification and chunk assembly; (5) only then enable a bounded worker with explicit budgets and stop conditions.


## 4.2 Provider failure ledger and retry foundation

**Partially implemented; worker execution remains disabled.** Provider failures are classified into rate limiting, exhausted quota, oversized payload, context overflow, transient service errors, concurrency pressure, permanent authentication/configuration failures and unknown errors. Retry-After and quota reset hints take precedence over bounded exponential backoff. The classifier is pure and deterministic when jitter is supplied by the caller. A separate capacity planner evaluates rolling RPM/TPM windows, input/output ceilings and concurrency. `PostgresCycleStore.reserve_provider_capacity()` now performs durable atomic admission using a provider/model/endpoint profile, transaction-scoped locks, an idempotency-key lock, shared account-level quota scopes and the database clock. Provider-derived profiles require a validity deadline and stale profiles fail closed. Provider reservations bind the stable idempotency key to the exact request-payload SHA-256 and persist request-body bytes plus estimated/actual token usage and cost; task-level and global daily/monthly budgets can be configured. Provider body-size ceilings are checked separately from token ceilings. Capacity deferrals have their own bounded counter and do not consume model retry attempts. Expired unsent reservations are releasable, while requests that may have been sent remain active/unknown until reconciled. Task lease renewal is available; capacity waits release the lease and schedule a durable recheck; bounded recovery maintenance handles due quota tasks and expired unsent reservations. Stale leases with ambiguous sends are quarantined rather than blindly reclaimed. Task completion is blocked while provider reservations are unresolved. These are callable persistence primitives; no scheduler invokes them yet.

A private append-only PostgreSQL attempt ledger records provider/model/endpoint, provider request ID, attempt number, HTTP status, classification, safe allowlisted headers, retry delay/reset metadata and a sanitized summary. It deliberately excludes prompts, response bodies and credentials. Recording an attempt and transitioning the leased task are one database transaction: retryable transient failures return the task to pending at a future available_at and release the worker; quota, oversized/context payload and unknown cases become blocked; permanent configuration failures become failed.

Quota recovery now has a durable foundation: the queue records an explicit block reason and optional reset timestamp. `PostgresCycleStore.recover_due_quota_tasks()` requeues only quota-blocked tasks with a known reset time that has arrived; unrelated blocked tasks and quota tasks without reset timestamps remain blocked. Concurrent scheduler calls use row locking with `SKIP LOCKED`, and exhausted attempt budgets become terminal failures. Migration `0005_quota_task_recovery.sql` is deployed.

Adaptive payload handling now has a deterministic splitter, stable chunk IDs, per-chunk/total SHA-256 validation, idempotent acknowledgement validation, durable manifest/chunk/ack tables, and an assembly operation that marks a payload `ready_for_model` only after complete integrity verification. Migration `0006_durable_payload_chunks.sql` is deployed. Stateless endpoints must receive one fully reassembled request; chunk acknowledgements do not imply model-side context continuity.

CI run [44123775757](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/44123775757) passed for the implementation and tests. These are persistence and orchestration primitives, not a live scheduler or provider adapter. The provider adapter interface contract is defined but not connected to a live transport. Remaining work includes provider-specific adapters that perform authoritative lookup and supply trusted reconciliation evidence, plus live limit/pricing discovery; profile and budget configuration; scheduler invocation and recovery; account quota scope mapping and provider-specific window semantics; provider-specific idempotency/retrieval integration and human-visible evidence review for ambiguous delivery; provider tokenizers and provider-specific rate-window semantics; remote chunk transport; real service-role application round-trip tests; and end-to-end model execution. Do not run a worker until those transitions and provider adapters are integrated and verified.
