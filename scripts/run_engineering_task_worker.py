"""Run one universal YJ64 engineering parent task from a configured worker host."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation import (
    create_engineering_worker_runner,
    create_reference_engineering_dispatcher,
)
from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    if not database_url:
        print("YJ64_DATABASE_URL is not configured.", file=sys.stderr)
        return 2

    worker_id = os.environ.get("YJ64_ENGINEERING_WORKER_ID", "yj64-engineering-worker").strip()
    if not worker_id:
        print("YJ64_ENGINEERING_WORKER_ID must be non-empty.", file=sys.stderr)
        return 2

    cad_workspace = os.environ.get("YJ64_CAD_WORKSPACE", "").strip() or None
    stage = "configuration"
    try:
        dispatcher = create_reference_engineering_dispatcher(
            cad_workspace=cad_workspace,
        )
        stage = "store_init"
        store = PostgresCycleStore(database_url)
        stage = "runner_init"
        runner = create_engineering_worker_runner(
            store,
            dispatcher=dispatcher,
            worker_id=worker_id,
            lease_seconds=300,
            recovery_limit=100,
        )
        stage = "run_once"
        result = runner.run_once()
    except Exception as exc:
        detail = str(exc).splitlines()[0][:180].replace(database_url, "[REDACTED]")
        print(json.dumps({
            "ok": False,
            "worker": "engineering",
            "stage": stage,
            "error_type": type(exc).__name__,
            "diagnostic": detail,
        }), file=sys.stderr)
        return 1

    print(json.dumps({
        "ok": result.get("status") in {"completed", "idle", "blocked", "waiting"},
        "worker": "engineering",
        "result": result,
        "capabilities": ["engineering.dispatch"],
        "cad_workspace_configured": cad_workspace is not None,
        "scope": "universal_parent_task_ingress_with_reference_engineering_backends",
    }, default=str, separators=(",", ":")))
    return 0 if result.get("status") in {"completed", "idle", "blocked", "waiting"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
