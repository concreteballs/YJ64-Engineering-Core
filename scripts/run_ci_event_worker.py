"""Run one safe CI-event queue task from a scheduled GitHub Actions runner.

This worker only verifies persisted CI metadata. It does not inspect or execute
repository code, call an LLM, or launch engineering jobs.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore
from yj64_engineering_core.automation.worker import TaskExecutionResult, WorkerRunner


EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
EXPECTED_WORKFLOW = "Python tests"
EXPECTED_BRANCH = "main"
VALID_CONCLUSIONS = {
    "success", "failure", "cancelled", "timed_out",
    "action_required", "neutral", "skipped", "stale",
}


def process_ci_event(task: dict, context) -> TaskExecutionResult:
    """Verify the durable event referenced by a queue task; perform no side effects."""
    payload = task.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return TaskExecutionResult("blocked", "invalid_ci_event_payload")
    if not isinstance(payload, dict):
        return TaskExecutionResult("blocked", "invalid_ci_event_payload")

    event_id = payload.get("event_id")
    if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id < 1:
        return TaskExecutionResult("blocked", "invalid_ci_event_id")

    event = context.store.get_ci_event(event_id)
    if event is None:
        return TaskExecutionResult("blocked", "ci_event_not_found")

    if (
        event.get("event_id") != event_id
        or event.get("repository") != EXPECTED_REPOSITORY
        or event.get("workflow") != EXPECTED_WORKFLOW
        or event.get("branch") != EXPECTED_BRANCH
        or event.get("conclusion") not in VALID_CONCLUSIONS
    ):
        return TaskExecutionResult("blocked", "ci_event_scope_rejected")

    run_id = event.get("run_id")
    attempt = event.get("run_attempt")
    sha = event.get("commit_sha")
    run_url = event.get("run_url")
    if (
        not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1
        or not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1
        or not isinstance(sha, str) or len(sha) != 40
        or any(ch not in "0123456789abcdef" for ch in sha)
        or not isinstance(run_url, str)
        or not run_url.startswith(
            f"https://github.com/{EXPECTED_REPOSITORY}/actions/runs/{run_id}"
        )
    ):
        return TaskExecutionResult("blocked", "ci_event_integrity_rejected")

    # Completion means only that the persisted event passed validation.
    # A separate future handler will perform CI analysis and roadmap progression.
    return TaskExecutionResult("completed")


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    if not database_url:
        print("YJ64_DATABASE_URL is not configured.", file=sys.stderr)
        return 2

    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    worker_id = f"gha-ci-event-{run_id}-{run_attempt}"

    try:
        store = PostgresCycleStore(database_url)
        runner = WorkerRunner(
            store,
            worker_id=worker_id,
            handlers={"process_ci_event": process_ci_event},
            lease_seconds=300,
            recovery_limit=100,
            allowed_task_types=["process_ci_event"],
        )
        result = runner.run_once()
    except Exception as exc:
        print(
            json.dumps({
                "ok": False,
                "error_type": type(exc).__name__,
                "message": "Worker invocation failed; details suppressed.",
            }),
            file=sys.stderr,
        )
        return 1

    print(json.dumps({
        "ok": result.get("status") in {"completed", "idle", "blocked"},
        "worker": "ci_event_verifier",
        "result": result,
        "scope": "persisted_ci_event_validation_only",
    }, default=str, separators=(",", ":")))
    return 0 if result.get("status") in {"completed", "idle", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
