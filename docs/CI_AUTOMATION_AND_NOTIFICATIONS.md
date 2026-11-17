# CI Automation and Completion Notifications

## Current verified implementation

- `.github/workflows/tests.yml` runs the Python, FEM and CAD test suite.
- `.github/workflows/notify-ci-completion.yml` listens for completion of the `Python tests` workflow on pushes to `main`.
- `scripts/record_ci_completion.py` validates the GitHub `workflow_run` payload and writes the event directly to Supabase PostgreSQL.
- `src/yj64_engineering_core/automation/postgres_store.py` persists CI events idempotently and enqueues `process_ci_event` tasks in the existing `yj64_task_queue`.
- `src/yj64_engineering_core/automation/worker.py` provides a one-task-per-invocation worker with leases, recovery, completion, retry and blocked states.
- `scripts/run_ci_event_worker.py` validates one persisted CI event without executing repository code or making provider calls.
- `.github/workflows/scheduled-ci-event-worker.yml` starts that bounded worker every five minutes and supports manual dispatch.

The CI completion path no longer depends on the Vercel webhook endpoint. The GitHub Actions workflow uses only the repository secret `YJ64_DATABASE_URL`. The queue remains the single durable queue; no parallel queue was introduced.

## Current worker safety boundary

The scheduled worker claims only `process_ci_event` tasks. Other task types are left untouched. Each invocation claims at most one task and has a four-minute job timeout. PostgreSQL leases and `FOR UPDATE SKIP LOCKED` protect concurrent claims.

The current `process_ci_event` handler verifies that the referenced database event exists and that its repository, workflow, branch, conclusion, commit SHA and run URL are within the expected scope. It then acknowledges the event as validated.

**This is not yet CI diagnosis or autonomous engineering.** The handler does not fetch GitHub job details or logs, call an LLM, read and select roadmap tasks, modify source code, create commits, or launch engineering jobs. Those capabilities remain disabled until their own handlers, policies and tests are implemented.

## Required configuration

The scheduled worker requires the repository Actions secret:

- `YJ64_DATABASE_URL`: PostgreSQL connection string for the YJ64 Supabase database.

Keep the connection string server-side. Never put it in source files, workflow output, issues or chat messages. The worker does not require the old Vercel webhook URL or webhook bearer secret.

## Safe development loop — current stage

1. GitHub Actions completes the Python test workflow.
2. The completion workflow validates and persists the event directly to PostgreSQL.
3. PostgreSQL atomically inserts one deduplicated `process_ci_event` task.
4. The scheduled worker claims at most one matching task using the existing lease mechanism.
5. The worker validates the persisted event and acknowledges it, or leaves it blocked with a classified reason.
6. A later stage will add bounded GitHub run inspection, roadmap task selection, model-provider execution, validation and continuation.

## Remaining activation work

- Verify that the scheduled worker runs successfully against the live Supabase queue and processes a real pending CI event.
- Add a durable audit/result record for worker outcomes.
- Implement safe GitHub workflow/job inspection and evidence capture.
- Implement roadmap task selection and session-independent checkpoints.
- Add provider adapters, server-side secrets, quotas, cost limits and retry policies before any model calls.
- Add pause/resume/kill switch, monitoring and notifications.
- Demonstrate that the worker continues while the user's phone is offline and recovers after interruption.

## Important ChatGPT conversation limitation

An external worker cannot resume this exact ChatGPT conversation. A separate event/notification bridge is required before automatic continuation inside this chat can be claimed.

The current system is a working CI-event persistence pipeline with a bounded scheduled event-validation worker. It is not yet a fully autonomous engineering cycle.
