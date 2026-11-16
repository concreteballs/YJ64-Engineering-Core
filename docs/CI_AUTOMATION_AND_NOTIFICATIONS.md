# CI Automation and Completion Notifications

## Current implementation

The repository has:
- .github/workflows/tests.yml — Python/FEM/CAD test workflow.
- .github/workflows/notify-ci-completion.yml — completion-event sender for pushes to main.
- api/index.py — authenticated Vercel ingress for GitHub Actions completion events.
- migrations/0001_autonomous_cycle.sql — PostgreSQL schema for durable CI events and queued tasks.
- src/yj64_engineering_core/automation/postgres_store.py — idempotent event persistence, queue insertion, leased task claiming, bounded retry, completion and blocking primitives.

The ingress validates repository, branch, workflow, event type, run identity, commit SHA, conclusion and run URL. It then stores the event in PostgreSQL and creates one process_ci_event task. A uniqueness constraint on repository + run_id + run_attempt deduplicates webhook retries.

The queue supports atomic claims with FOR UPDATE SKIP LOCKED, worker leases, retry limits, completion and blocked states. This is a software foundation; it is not yet a deployed autonomous worker.

## GitHub configuration

Add these repository Actions secrets under Settings -> Secrets and variables -> Actions:
- YJ64_CI_WEBHOOK_URL: canonical HTTPS Vercel production endpoint, currently intended to be https://yj-64-engineering-core-kakq.vercel.app/api.
- YJ64_CI_WEBHOOK_SECRET: high-entropy random secret shared with the Vercel receiver.

Never put either value in source files, workflow YAML, issues, logs or chat messages.

## Vercel configuration

The Vercel deployment needs:
- YJ64_CI_WEBHOOK_SECRET: same value as the GitHub Actions secret.
- YJ64_DATABASE_URL: PostgreSQL connection string for the dedicated YJ64 database.

Do not expose the database URL to browser/client code. Use a server-side secret and a provider-supported pooled connection string where appropriate.

The SQL migration in migrations/0001_autonomous_cycle.sql must be applied once to the database before the receiver can persist events. The API intentionally returns a configuration/service error if the database or schema is unavailable; it does not silently downgrade to an in-memory queue.

## Receiver behaviour

- GET /api reports service identity and whether a database URL is configured; it does not reveal secrets.
- POST /api requires the bearer secret, validates the event and persists it.
- A successful response is HTTP 202 and reports whether the event was a duplicate and whether a processing task was enqueued.
- Duplicate webhook deliveries do not create duplicate CI events or duplicate processing tasks.
- The endpoint does not run model inference, execute repository code, modify GitHub or resume this ChatGPT conversation.

## Safe development loop

1. GitHub Actions reports completion.
2. The receiver authenticates, validates, deduplicates and persists the event.
3. A durable queue task becomes available to a cloud worker.
4. The worker checks the exact commit, workflow result, job summaries and failure logs.
5. On success, it selects the next incomplete roadmap task.
6. On failure, it diagnoses and permits only bounded repair attempts.
7. Every code change triggers CI again.
8. Stop on ambiguous requirements, destructive changes, permission requests, paid external calls, purchases, physical actuation or safety-critical decisions.
9. Preserve task history and record commit/run references; never claim success without a completed successful run.

## Remaining activation and worker work

Not yet complete:
- Apply the PostgreSQL migration to a real database.
- Configure and verify the GitHub and Vercel secrets without exposing their values.
- Verify the production deployment and test an authenticated webhook end to end.
- Deploy a separate cloud worker that claims queue tasks, reads the roadmap, checks CI details and advances tasks.
- Configure a model provider through server-side secrets and bounded budgets.
- Add worker scheduling/wakeup, pause/resume/kill switch, monitoring and external notifications.
- Demonstrate that the worker continues after the user's phone is offline and recovers after restart.

## Important ChatGPT conversation limitation

A GitHub webhook can notify an external receiver or start a separate cloud agent. It cannot, by itself, resume this exact ChatGPT conversation. A supported ChatGPT background-task/event integration must be connected before automatic continuation inside this chat can be claimed.

The system is therefore currently a partially implemented cloud-cycle foundation, not a fully autonomous loop.
