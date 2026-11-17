"""Persist GitHub Actions completion events directly to the YJ64 PostgreSQL queue.

This replaces the Vercel HTTP hop for CI completion events. It does not run
engineering tasks; it only validates and enqueues an idempotent event.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"
EXPECTED_WORKFLOW = "Python tests"
EXPECTED_BRANCH = "main"
VALID_CONCLUSIONS = {
    "success", "failure", "cancelled", "timed_out",
    "action_required", "neutral", "skipped", "stale",
}


def build_event(payload: dict) -> dict:
    """Validate the GitHub workflow_run payload and return the DB event."""
    if not isinstance(payload, dict):
        raise ValueError("event_payload_must_be_object")
    repository = payload.get("repository")
    run = payload.get("workflow_run")
    if not isinstance(repository, dict) or not isinstance(run, dict):
        raise ValueError("workflow_run_payload_missing")
    if repository.get("full_name") != EXPECTED_REPOSITORY:
        raise ValueError("repository_scope_rejected")
    if (
        run.get("name") != EXPECTED_WORKFLOW
        or run.get("event") != "push"
        or run.get("head_branch") != EXPECTED_BRANCH
    ):
        raise ValueError("workflow_scope_rejected")

    run_id = run.get("id")
    attempt = run.get("run_attempt")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise ValueError("invalid_run_id")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt <= 0:
        raise ValueError("invalid_run_attempt")

    commit_sha = run.get("head_sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("invalid_commit_sha")
    conclusion = run.get("conclusion")
    if conclusion not in VALID_CONCLUSIONS:
        raise ValueError("invalid_conclusion")

    run_url = run.get("html_url")
    prefix = f"https://github.com/{EXPECTED_REPOSITORY}/actions/runs/"
    if (
        not isinstance(run_url, str)
        or not run_url.startswith(prefix)
        or not run_url[len(prefix):].split("/", 1)[0].isdigit()
    ):
        raise ValueError("invalid_run_url")

    return {
        "repository": EXPECTED_REPOSITORY,
        "run_id": run_id,
        "run_attempt": attempt,
        "workflow": EXPECTED_WORKFLOW,
        "conclusion": conclusion,
        "commit_sha": commit_sha,
        "branch": EXPECTED_BRANCH,
        "run_url": run_url,
    }


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not database_url or not event_path:
        print("Required GitHub Actions database/event configuration is missing.", file=sys.stderr)
        return 2
    try:
        with open(event_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        event = build_event(payload)
        result = PostgresCycleStore(database_url).record_ci_event(event)
    except Exception as exc:
        # Do not print exception text: it may contain connection details.
        print(f"CI event persistence failed ({type(exc).__name__}).", file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": True,
        "accepted": True,
        "duplicate": bool(result.get("duplicate")),
        "task_enqueued": bool(result.get("task_enqueued")),
        "event_id": result.get("event_id"),
        "transport": "github_actions_direct_postgres",
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
