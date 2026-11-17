# YJ64 — Observability, Log Monitoring & Diagnostics
Status: **Planned cross-cutting foundation; limited diagnostic primitives exist**

## Purpose
Make every failure explainable from evidence. The system must answer what happened, where, when, in which execution, with which inputs and versions, what changed, what was observed, and what corrective action is justified. The objective is to prevent blind debugging, repeated failed attempts and waste of engineering time, compute and model tokens.

This is not merely a log viewer. It is a shared capability used by every module and by the Autonomous Engineering Cycle.

## Current verified baseline
- api/index.py extracts validated PostgreSQL SQLSTATE from psycopg .sqlstate / .pgcode, maps validated codes to safe diagnostic categories, and avoids returning raw exception text or connection secrets.
- CI workflow logs and job summaries can be inspected manually.
- The webhook receiver returns a bounded diagnostic category on persistence failure.
- The repository does not yet contain a general observability package, unified telemetry schema, distributed tracing, metrics/alerting backend, diagnostic-bundle pipeline or operator dashboard.
- The current live HTTP 503 is still unresolved. A category such as database_schema_error narrows the failure class; it does not by itself prove the root cause.

## Architecture

### 1. Common instrumentation contract
Every component emits structured events with:
- UTC timestamp and severity;
- service, component, module/discipline, agent and environment;
- event name and stable error code/category;
- trace_id, span_id, correlation_id, task_id and parent_task_id;
- repository, branch, commit SHA, workflow/run/job/step IDs where applicable;
- deployment/build version and dependency/solver versions;
- operation name, duration, retry/attempt number and outcome;
- safe typed context: input/artifact hashes, units, relevant configuration fingerprint, resource usage and state transition;
- exception type, validated SQLSTATE/HTTP status/exit code and sanitized stack trace or log reference when safe.

Never log credentials, API keys, bearer tokens, database URLs, private keys, raw authorization headers or unredacted personal data. Redaction must happen before persistence/export.

### 2. Three complementary telemetry signals
- Logs: timestamped structured records for discrete events, errors and state changes.
- Metrics: bounded counters, gauges and histograms for success/failure rates, latency, queue depth/age, retry counts, worker leases, solver duration, resource use and API/compute spend.
- Traces: end-to-end spans across GitHub Actions → webhook → Vercel receiver → PostgreSQL event/queue → dispatcher → worker → agent/module → solver/adapter → result artifact → validation.

All three share correlation context so one task or failed build can be followed end to end. Use OpenTelemetry-compatible semantics/export where practical; keep core contracts vendor-neutral.

### 3. Diagnostic bundle per failed or suspicious task
Automatically assemble a bounded, immutable bundle containing task/event/run IDs, exact commit/deployment versions, workflow/job/failed-step summaries, relevant sanitized logs, exception/SQLSTATE/HTTP/exit codes, timing, retry history, queue state transitions, dependency/tool versions, non-secret environment/config fingerprints, artifact hashes/links, related traces and key metrics, and expected versus observed validation results.

Preserve enough context to reproduce the failure. Apply size caps, sampling and retention policies. Keep full raw output only where justified; retain compact summaries and hashes longer.

### 4. Diagnostic and repair assistant
A diagnostic agent/service may classify a failure using evidence, correlate events, rank likely causes with confidence, identify missing evidence, request the cheapest targeted check, propose the smallest corrective change and regression test, then verify the exact changed commit through CI.

It must distinguish confirmed cause from hypothesis. It must not invent missing logs, claim a fix without passing validation, repeat the same uninformative retry, or perform destructive/paid/physical operations without required approval. Enforce attempt, token, time and cost budgets.

### 5. Health, alerting and operator view
Provide liveness/readiness/dependency health checks (distinguish process alive from database/queue actually usable), alerts for failed delivery, growing/old queue, stuck leases, repeated retries, worker silence, elevated error rate, resource exhaustion and budget thresholds, and task/run drill-down from one correlation ID.

Health endpoints must not expose secrets or sensitive internals.

### 6. Reliability, privacy and cost
Telemetry failure must not silently break core task execution; use bounded buffering and explicit degraded/drop counters. The task queue must not depend on an observability backend. Use sampling and cardinality limits, retention/access/deletion policies, source-side redaction, and bounded telemetry volume/storage/external calls/diagnostic inference cost.

## Implementation sequence
1. Define and test the versioned event/error schema and redaction rules.
2. Add correlation propagation to webhook, queue, dispatcher, worker and agent task contracts.
3. Standardize structured logging and safe exception classification across Python modules and API handlers.
4. Create diagnostic-bundle generation and immutable artifact references.
5. Add baseline metrics for queue, CI, worker, agents, solvers, retries, latency and cost.
6. Add distributed tracing across the full task lifecycle.
7. Add health/readiness checks that actively verify dependencies without leaking details.
8. Add alert rules and a minimal operator drill-down/status view.
9. Add evidence-based diagnostic triage with bounded, approval-aware repair proposals.
10. Add fault-injection tests: database unavailable, schema mismatch, auth failure, duplicate event, expired lease, worker crash, solver timeout, invalid artifact and telemetry backend outage.
11. Demonstrate a deliberately injected fault being localized to the correct component and corrected without blind repository-wide changes.

## Acceptance criteria
- One task/run ID reveals the complete execution path and exact failed component/step.
- Every production failure has a stable category and useful diagnostic bundle, or an explicit reason evidence is unavailable.
- Logs, metrics and traces correlate across service boundaries.
- Secret-redaction tests prove credentials never enter telemetry.
- Alerts identify stuck/failed work before it silently accumulates.
- Diagnostic triage proposes evidence-backed next checks and avoids repeated uninformative retries.
- A fault-injection exercise demonstrates root-cause localization and a validated minimal fix.

## Integration rule
Observability is a cross-cutting platform capability, not a separate discipline silo. It is built into Stage 0 of the strategic programme and mandatory in every later module's onboarding contract. The autonomous cycle's acceptance gate must include diagnostic evidence for successful and failed runs.
