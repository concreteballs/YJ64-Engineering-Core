# YJ64 Engineering Core — Autonomous Cycle and Master Roadmap

Last reconciled: 2026-11-17
Repository: concreteballs/YJ64-Engineering-Core
Authorized branch: main

This document is the execution index for the autonomous development cycle. It separates verified implementation from planned work. The detailed subsystem ledger remains in IMPLEMENTATION_STATUS.md; this file records the current control-loop priority and the order in which the remaining master plan should be executed.

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
- Latest verified main test run at this reconciliation: [43981929835](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/43981929835), conclusion success, commit 2a3245a91d4fc50e4fce441c498ce5b33c135a24.
- The separate CI completion-webhook delivery run [43981930959](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/43981930959) failed with HTTP 401 Unauthorized. GitHub has both sender secrets configured, but the receiver rejected the bearer token. The two secret values must be aligned; values must not be exposed.
- PostgreSQL database, migration application, Vercel environment configuration and end-to-end persistence are not yet verified. The cloud worker and autonomous continuation are not implemented.
- This confirms software tests passed; it does not mean the autonomous cloud loop is operational.

## 2. Current priority: finish the autonomous engineering cycle

Do not start broad implementation of every engineering discipline until this cycle is operational. The cycle must be capable of taking the next incomplete task from this roadmap, executing bounded work, validating it, recording the result and continuing without requiring the user's phone to remain online.

### Cycle milestone A — reliable event delivery

Implemented in code:
- GitHub Actions completion-event sender.
- Authenticated receiver with strict repository, branch, workflow, event, run identity, commit and URL validation.
- Idempotent persistence design and duplicate protection.

Still required:
- Align GitHub YJ64_CI_WEBHOOK_SECRET with the Vercel YJ64_CI_WEBHOOK_SECRET; the latest delivery test returned HTTP 401.
- Verify the canonical Vercel production URL and deployed version.
- Verify the receiver returns an authenticated 202 after database setup.
- Record and verify successful end-to-end delivery; do not treat configured secrets as proof of delivery.

### Cycle milestone B — durable task state

Implemented in code:
- PostgreSQL schema migration for CI events and task queue.
- Persistent event store and idempotent process_ci_event enqueue.
- Atomic queue claim with FOR UPDATE SKIP LOCKED and expiring worker lease.
- Bounded retry, completion and blocked-state operations.
- Automated tests using a controlled database double.

Still required:
- Create/connect the production PostgreSQL database and apply migrations/0001_autonomous_cycle.sql.
- Configure YJ64_DATABASE_URL in Vercel using a server-side pooled connection string.
- Verify real persistence, deduplication, queue claims and restart recovery against the live database.
- Add task history, dependency/parent linkage, artifacts/log references and backup/retention policy as the worker contract matures.

### Cycle milestone C — cloud worker and authorized agent
- Deploy a separate cloud worker that can wake from queued work independently of the user's device.
- Give it access only to this repository and the authorized main workflow; do not grant unrelated repositories.
- Connect an explicitly configured model provider through server-side secrets. No model API key is assumed to exist.
- Worker reads this roadmap and implementation ledger, chooses the next unblocked task, prepares a bounded change, runs local checks and submits the change to the authorized branch.
- Preserve a complete task/decision/provenance record.
- Do not claim this worker can resume the exact ChatGPT conversation. A supported notification bridge is a separate integration.

### Cycle milestone D — validation and closed-loop continuation
- On every change, wait for the exact GitHub Actions run associated with its commit.
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
8. Pause/kill switch and budget limits are demonstrated.

Until all acceptance criteria pass, describe the system as partially implemented, not autonomous.

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
- Update this roadmap and IMPLEMENTATION_STATUS.md as part of the same task that changes implementation status.
