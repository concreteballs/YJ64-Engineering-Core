"""Run one durable YJ-64 Council Gateway queue task from GitHub Actions."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.council_result_consumer import (
    handle_council_result_ready,
)
from yj64_engineering_core.automation.council_tasks import (
    POLL_TASK,
    RESULT_READY_TASK,
    SUBMIT_TASK,
    handle_poll_council_request,
    handle_submit_council_request,
)
from yj64_engineering_core.automation.postgres_store import PostgresCycleStore
from yj64_engineering_core.automation.worker import WorkerRunner


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    if not database_url:
        print("YJ64_DATABASE_URL is not configured.", file=sys.stderr)
        return 2
    if not os.environ.get("YJ64_COUNCIL_API_URL", "").strip():
        print("YJ64_COUNCIL_API_URL is not configured.", file=sys.stderr)
        return 2
    if not os.environ.get("YJ64_COUNCIL_AGENT_TOKEN", "").strip():
        print("YJ64_COUNCIL_AGENT_TOKEN is not configured.", file=sys.stderr)
        return 2
    if not (os.environ.get("YJ64_COUNCIL_SUPABASE_API_KEY", "").strip() or os.environ.get("YJ64_COUNCIL_API_PUBLISHABLE_KEY", "").strip() or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()):
        print("A Supabase publishable key (YJ64_COUNCIL_SUPABASE_API_KEY) is not configured.", file=sys.stderr)
        return 2
    if not os.environ.get("SUPABASE_URL", "").strip():
        print("SUPABASE_URL is not configured.", file=sys.stderr)
        return 2
    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        print("SUPABASE_SERVICE_ROLE_KEY is not configured.", file=sys.stderr)
        return 2

    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    worker_slot = os.environ.get("YJ64_WORKER_SLOT", "1").strip()
    if worker_slot not in {"1", "2", "3"}:
        print("YJ64_WORKER_SLOT must be between 1 and 3.", file=sys.stderr)
        return 2

    stage = "store_init"
    try:
        store = PostgresCycleStore(database_url)
        stage = "runner_init"
        runner = WorkerRunner(
            store,
            worker_id=f"gha-council-gateway-{run_id}-{run_attempt}-slot-{worker_slot}",
            handlers={
                SUBMIT_TASK: handle_submit_council_request,
                POLL_TASK: handle_poll_council_request,
                RESULT_READY_TASK: handle_council_result_ready,
            },
            lease_seconds=300,
            recovery_limit=100,
            allowed_task_types=[SUBMIT_TASK, POLL_TASK, RESULT_READY_TASK],
        )
        stage = "run_once"
        result = runner.run_once()
    except Exception as exc:
        detail = str(exc).splitlines()[0][:180]
        for secret in (
            database_url,
            os.environ.get("YJ64_COUNCIL_AGENT_TOKEN", ""),
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
        ):
            if secret:
                detail = detail.replace(secret, "[REDACTED]")
        print(json.dumps({
            "ok": False,
            "stage": stage,
            "error_type": type(exc).__name__,
            "diagnostic": detail,
        }), file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": result.get("status") in {"completed", "idle", "blocked", "waiting"},
        "worker": "council_gateway",
        "result": result,
        "scope": "native_yj64_council_submit_poll_and_result_consumption",
    }, default=str, separators=(",", ":")))
    return 0 if result.get("status") in {"completed", "idle", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
