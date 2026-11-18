"""Run one budget-gated CI-log analysis task from GitHub Actions."""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.ci_log_analysis import (
    GEMINI_MODEL,
    GEMINI_PROFILE,
    process_ci_log_analysis,
)
from yj64_engineering_core.automation.gemini_adapter import GeminiGenerateContentAdapter
from yj64_engineering_core.automation.postgres_store import PostgresCycleStore
from yj64_engineering_core.automation.supabase_storage import SupabaseStorageArtifactStore
from yj64_engineering_core.automation.worker import WorkerRunner


def main() -> int:
    required = (
        "YJ64_DATABASE_URL", "GEMINI_API_KEY",
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        print(json.dumps({"ok": False, "error": "required_server_secrets_missing", "names": missing}))
        return 2

    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    worker_id = f"gha-ci-log-analysis-{run_id}-{run_attempt}"

    try:
        store = PostgresCycleStore(os.environ["YJ64_DATABASE_URL"])
        store.set_provider_limit_profile(
            GEMINI_PROFILE,
            capacity_scope="gemini-free-tier-yj64-account",
            profile_source="operator_config",
        )
        usage = store.get_cycle_usage()
        limits = usage.get("limits") or {}
        try:
            daily_cost = Decimal(str(limits.get("daily_cost_usd")))
            monthly_cost = Decimal(str(limits.get("monthly_cost_usd")))
        except (InvalidOperation, TypeError):
            print(json.dumps({"ok": False, "error": "explicit_zero_cost_budget_required"}))
            return 2
        if daily_cost != 0 or monthly_cost != 0:
            print(json.dumps({"ok": False, "error": "zero_cost_budget_guard_rejected"}))
            return 2

        artifacts = SupabaseStorageArtifactStore.from_environment(
            bucket="yj64-private-artifacts",
            max_upload_bytes=6 * 1024 * 1024,
        )
        adapter = GeminiGenerateContentAdapter(
            model=GEMINI_MODEL,
            limit_profile=GEMINI_PROFILE,
            artifact_store=artifacts,
        )
        runner = WorkerRunner(
            store,
            worker_id=worker_id,
            handlers={
                "analyze_ci_logs": lambda task, context: process_ci_log_analysis(
                    task, context, adapter=adapter, artifact_store=artifacts,
                    profile=GEMINI_PROFILE,
                )
            },
            lease_seconds=300,
            recovery_limit=100,
            allowed_task_types=["analyze_ci_logs"],
        )
        result = runner.run_once()
        print(json.dumps({
            "ok": result.get("status") in {"completed", "idle", "blocked"},
            "worker": "ci_log_analysis",
            "model": GEMINI_MODEL,
            "cost_guard_usd": "0",
            "result": result,
        }, default=str, separators=(",", ":")))
        return 0 if result.get("status") in {"completed", "idle", "blocked"} else 1
    except Exception as exc:
        # Do not print provider bodies, credentials, or arbitrary exception text.
        print(json.dumps({
            "ok": False,
            "worker": "ci_log_analysis",
            "error_type": type(exc).__name__,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
