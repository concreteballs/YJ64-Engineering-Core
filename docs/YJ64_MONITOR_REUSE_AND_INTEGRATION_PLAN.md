# YJ64 Monitor Prototype — Reuse Assessment and Integration Plan

Status: **Source reviewed; shared event-contract foundation started in YJ64 Engineering Core. Android monitor is not yet integrated.**

Source repository (read-only reference): [concreteballs/yj64-clean-bial2modFun5](https://github.com/concreteballs/yj64-clean-bial2modFun5)

Target repository: `concreteballs/YJ64-Engineering-Core`, branch `main`.

## Executive decision

Reuse the prototype's proven architectural ideas and portable protocol concepts; do not copy the Android application wholesale into the engineering kernel.

The prototype demonstrates a useful producer/collector pattern:
- an embedded diagnostic agent emits versioned `yj64.diagnostic.v1` events;
- reports carry an event/report identifier, agent, timestamp, event name and structured data;
- a standalone Android monitor receives reports and durably appends JSONL before acknowledging;
- the producer retains a local spool when delivery fails and retries forwarding later;
- the monitor can collect Android process-exit/crash evidence, display/copy reports and upload them to GitHub.

This is a valuable device-side diagnostic edge. YJ64 Engineering Core needs a broader, platform-neutral observability service that accepts events from Python modules, agents, CI, cloud workers, APIs, solver adapters and optional device monitors.

## Verified source findings

Reviewed source files:
- `README.md`
- `services/internal_monitor.py`
- `monitor-app/app/src/main/java/org/blackmirror/yj64monitor/DiagnosticReportProvider.java`
- `monitor-app/app/src/main/java/org/blackmirror/yj64monitor/MonitorActivity.java`
- `reports/latest-report.jsonl`

### Reusable concepts

1. **Versioned event envelope:** `yj64.diagnostic.v1` is already used in source reports.
2. **Durable acknowledgement:** the Android ContentProvider returns success only after appending and syncing the JSONL report.
3. **Offline spool:** the embedded agent preserves reports locally and forwards them when the receiver becomes available.
4. **Self-diagnostics:** startup checks cover configuration, writable storage, process state and target visibility.
5. **Lifecycle evidence:** events include startup, readiness, launch attempts and process-exit details.
6. **Operator workflow:** inspect, copy and explicitly upload a diagnostic report.

### Gaps and risks to resolve before production reuse

- The prototype is Android-specific; its Java ContentProvider and Android process-exit APIs are not the common engineering-core transport.
- The README describes loopback TCP on port 9333, while the reviewed Python sender currently calls an Android ContentProvider through `ContentResolver.call`. The documented and implemented transport need reconciliation.
- The README says a real HTTPS endpoint is not configured. The optional HTTPS uploader in the Python service does not itself provide durable acknowledgement, authentication policy, retry state or verified cloud persistence.
- The monitor's GitHub destination constant currently names `yj64-clean-bial2modFun`, omitting the final `5` from the source repository name. Treat this as a configuration defect to fix if that upload path is reused.
- The current event envelope is too small for engineering-wide correlation: it lacks standard trace/span/correlation/task IDs, repository commit/deployment identity, operation duration, typed error fields, solver provenance and artifact references.
- Sensitive values can enter arbitrary event data. The common platform must redact before persistence/export and must never accept secrets as diagnostic context.
- Some diagnostic paths catch and ignore errors (for example local event append); a monitor must report telemetry loss/degraded state rather than silently implying complete coverage.
- The current Android report stream is append-only JSONL without a defined retention, rotation, size cap, integrity chain or backpressure policy.
- The source code is a prototype, not evidence of production-grade security, availability, scale or cross-module integration.

## Target architecture

Keep three layers separate:

### A. Common YJ64 event contract (portable core)

A versioned, vendor-neutral event schema shared by all producers. It carries:
- stable event ID, schema version, UTC timestamp, severity, event name and outcome;
- service, component, discipline/module, agent and environment;
- trace, span, correlation, task and parent-task IDs;
- repository, branch, commit, workflow/job/run and deployment identity where applicable;
- operation, duration, attempt and stable error classification;
- validated HTTP status, SQLSTATE or process exit code where applicable;
- safe attributes and immutable artifact references/hashes.

The first dependency-free implementation is in `src/yj64_engineering_core/observability/events.py`. It validates the versioned envelope and redacts sensitive-key values, bearer credentials and URL user/password pairs before serialization. It is a contract foundation, not yet a collector, exporter, metrics backend or tracing runtime.

### B. Producer adapters

Each producer emits the common event contract:
- Python engineering modules and solver adapters;
- dispatcher, pipeline and autonomous queue/worker;
- CI webhook receiver and GitHub Actions;
- chemistry, artificial-muscle, robotics and other agents;
- Android monitor/device-side agents.

Device-specific collection stays in an adapter. The Android monitor can later translate its lifecycle/crash records into the common event envelope without making Android APIs dependencies of the engineering core.

### C. Shared collection and operator services

Add, in sequence:
1. bounded authenticated ingestion endpoint;
2. durable event store and immutable diagnostic-bundle references;
3. trace/correlation query across CI → webhook → queue → worker → agent → module → solver → validation;
4. metrics and alerting with cardinality/cost limits;
5. operator drill-down/status interface;
6. evidence-based diagnostic assistant.

The task queue must remain operational if the telemetry backend is degraded. Observability must never become a hidden dependency for engineering task execution.

## Migration sequence

1. **Contract:** stabilize and test the shared event schema, validation and redaction.
2. **Correlation:** add context propagation to API, CI event, task, dispatcher and worker contracts.
3. **Python instrumentation:** standardize structured events in the core, automation and solver adapters.
4. **Durable ingestion:** add authenticated bounded ingestion and persistence with explicit accepted/rejected acknowledgements.
5. **Offline delivery:** preserve the source prototype's spool-and-forward pattern in a platform-neutral producer library; define bounded disk usage, retry/backoff, deduplication and delivery checkpoints.
6. **Bundles:** assemble immutable, size-bounded diagnostic bundles linked to exact commit, deployment, task and artifact hashes.
7. **Metrics/traces/alerts:** add the remaining signals and operator view.
8. **Android adapter:** only then adapt the Android monitor to emit the common contract and use the shared ingestion endpoint; retain local crash collection and offline spool.
9. **Fault-injection acceptance:** demonstrate lost receiver, duplicate delivery, malformed event, secret redaction, backend outage, worker crash and end-to-end correlation.

## Mandatory module-onboarding gate

An engineering module is **not fully integrated** until all applicable checks pass:
- emits valid events using the current common schema;
- includes stable module/component identity and task/correlation context;
- reports start, completion, failure and degraded states;
- records input/output artifact hashes and relevant version/provenance data;
- classifies errors without leaking secrets or personal data;
- delivers events to shared collection or exposes a bounded, recoverable local spool with observable delivery state;
- has tests for schema conformance, redaction, duplicate handling and telemetry outage;
- can be diagnosed from the common operator view or an explicit evidence-gap report.

A module may be labelled **prototype-connected** while only local logging or a private diagnostic path exists. It must not be labelled fully integrated until the shared observability gate passes.

## Current implementation boundary

Implemented in Engineering Core:
- versioned `DiagnosticEvent` contract;
- event validation and JSON serialization;
- initial sensitive-key, bearer-token and URL-credential redaction tests.

Not yet implemented:
- ingestion API, durable telemetry store, spool/forwarder, OpenTelemetry SDK/exporters, metrics, traces, alerting, bundles, dashboard, Android adapter and full module instrumentation.

No claim is made that the original Android monitor has been copied, deployed or connected to the Engineering Core.
