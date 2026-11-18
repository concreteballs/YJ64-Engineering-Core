# CI Automation and Completion Notifications

## Current verified implementation

- \`.github/workflows/tests.yml\` runs the Python, FEM and CAD test suite.
- \`.github/workflows/notify-ci-completion.yml\` listens for completion of the \`Python tests\` workflow on pushes to \`main\`.
- \`scripts/record_ci_completion.py\` validates the GitHub \`workflow_run\` payload and writes the event directly to Supabase PostgreSQL.
- \`src/yj64_engineering_core/automation/postgres_store.py\` persists CI events idempotently and enqueues \`process_ci_event\` tasks in the existing \`yj64_task_queue\`.
- \`src/yj64_engineering_core/automation/worker.py\` provides a one-task-per-invocation worker with leases, recovery, completion, retry and blocked states.
- \`src/yj64_engineering_core/automation/ci_log_ingestion.py\` downloads the exact workflow-run attempt log archive through the read-only GitHub Actions API, bounds archive/member sizes, reads text logs without extracting files, and redacts known/common credential formats.
- \`scripts/run_ci_event_worker.py\` validates the persisted event, fetches its logs and stores a SHA-256-verified payload using the existing durable payload-manifest/chunk tables.
- \`.github/workflows/scheduled-ci-event-worker.yml\` starts that bounded worker every five minutes and supports manual dispatch.

The CI completion path does not depend on the Vercel webhook endpoint. The worker uses the repository's \`YJ64_DATABASE_URL\` secret and the per-run \`GITHUB_TOKEN\` with \`actions: read\`. The queue and payload tables are reused; no parallel queue or log database was introduced.

## Current worker safety boundary

The scheduled worker claims only \`process_ci_event\` tasks and processes at most one per invocation. PostgreSQL leases and \`FOR UPDATE SKIP LOCKED\` protect concurrent claims.

For a validated event, the worker retrieves logs for the exact \`run_id\` and \`run_attempt\`, rejects oversized or unsafe archives, redacts credentials, and persists a deterministic payload manifest plus content-addressed chunks. It reassembles the payload and verifies the complete SHA-256 before marking it \`ready_for_model\`. Log contents are explicitly marked as untrusted diagnostic data, not instructions. No repository code from the downloaded archive is executed.

**LLM transmission is not enabled yet.** The Gemini adapter is implemented and covered by offline tests, but it is not wired into the worker. The database currently has no configured provider limit profiles or global usage budget, and the exact model/pricing/limits have not been verified for the connected Gemini project. The logs are durably prepared for a model request, but no generation call is made and no automatic code repair is claimed.

## Required configuration

- \`YJ64_DATABASE_URL\`: PostgreSQL connection string for the YJ64 Supabase database.
- GitHub Actions \`GITHUB_TOKEN\`: automatically provided by GitHub Actions; the worker job requires \`actions: read\`.

Keep database and provider credentials server-side. Never put them in source files, workflow output, issues or chat messages.

## Safe development loop — current stage

1. GitHub Actions completes the Python test workflow.
2. The completion workflow validates and persists the event directly to PostgreSQL.
3. PostgreSQL atomically inserts one deduplicated \`process_ci_event\` task.
4. The scheduled worker claims at most one matching task using the existing lease mechanism.
5. The worker fetches the exact run-attempt logs, redacts and bounds them, then persists a verified payload.
6. The payload is ready for the provider adapter, and a durable `analyze_ci_logs` task is queued. The analysis worker is not yet enabled, so the payload is not transmitted to an LLM.

## Remaining activation work

- Verify the selected Gemini model's current metadata, pricing and project-specific limits; configure the verified provider profile and explicit global/task budgets before enabling generation.
- Wire the Gemini adapter into a separate `analyze_ci_logs` queue handler using the existing provider reservation, ambiguous-send and retry mechanisms. The queued task must remain unclaimed until the provider profile and global budget are configured.
- Add the equivalent Mistral adapter later as a quota-aware fallback; preserve split/retry-after-reset behaviour.
- Consume the prepared CI payload, persist a structured diagnosis and then implement bounded repair/rebuild orchestration.
- Implement roadmap task selection and session-independent checkpoints.
- Add pause/resume/kill switch, monitoring and notifications.
- Demonstrate that the worker continues while the user's phone is offline and recovers after interruption.

## Important ChatGPT conversation limitation

An external worker cannot resume this exact ChatGPT conversation. A separate event/notification bridge is required before automatic continuation inside this chat can be claimed.

The current system is a working CI-event persistence pipeline with bounded, redacted, integrity-verified log capture. It is not yet a live LLM-driven autonomous engineering cycle.


## Android emulator test bridge

The Android client repository `concreteballs/yj64-clean-bial2modFun5` runs
`.github/workflows/android-build.yml` on a GitHub-hosted Android 15 emulator.
The workflow builds Base and Monitor APKs, installs them in the x86_64 emulator,
launches both packages, checks Base-to-Monitor Content Provider IPC, and emits
job/logcat diagnostics.

GitHub `workflow_run` events do not cross repository boundaries. The Core
workflow `.github/workflows/poll-android-runtime-runs.yml` therefore polls the
public Android repository's exact workflow (main-branch push runs from the last
30 days) and persists completed attempts into the existing `yj64_ci_events`
table. Its unique key `(repository, run_id, run_attempt)` makes polling
idempotent. The existing `yj64_task_queue` receives `process_ci_event` tasks;
no second queue or cross-repository write token is introduced.

The log worker accepts only two explicit scopes:
- `concreteballs/YJ64-Engineering-Core` / `Python tests`
- `concreteballs/yj64-clean-bial2modFun5` / `.github/workflows/android-build.yml`

It downloads the exact attempt's logs, sanitizes them, stores a verified
payload manifest/chunks, and queues `analyze_ci_logs`. Android logs are fetched
anonymously because the app repository is public; the Core GitHub token is
never forwarded to another repository.

This bridge delivers emulator results to the durable analysis queue. It does
not yet enable live LLM analysis or autonomous code changes: those remain
gated by the configured $0 budget and a verified provider profile, and require
a separate analysis/repair worker.
