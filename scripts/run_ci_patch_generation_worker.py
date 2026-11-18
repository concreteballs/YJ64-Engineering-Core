"""Run one budget-gated, exact-commit CI patch-candidate task."""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.ci_log_analysis import GEMINI_MODEL, GEMINI_PROFILE
from yj64_engineering_core.automation.ci_patch_generation import process_ci_patch_generation
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
    worker_id = f"gha-ci-patch-generation-{run_id}-{run_attempt}"
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
                "generate_ci_patch": lambda task, context: process_ci_patch_generation(
                    task, context, adapter=adapter, artifact_store=artifacts,
                )
            },
            lease_seconds=600,
            recovery_limit=100,
            allowed_task_types=["generate_ci_patch"],
        )
        result = runner.run_once()
        saved = store.get_ci_patch_candidate(result["task_id"]) if isinstance(result.get("task_id"), int) else None
        if saved is not None:
            candidate = saved.get("candidate_json") or {}
            patch = candidate.get("patch") or {}
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
            if summary_path:
                lines = [
                    "## YJ64 CI patch candidate",
                    "",
                    f"- Status: `{saved.get('candidate_status')}`",
                    f"- Proposal task: `{saved.get('proposal_task_id')}`",
                    f"- Source commit: `{(candidate.get('source') or {}).get('commit_sha', 'unknown')}`",
                    f"- Current HEAD: `{(candidate.get('source') or {}).get('current_head_sha', 'not inspected')}`",
                    "- Automatic apply/commit: **disabled**",
                    "- Human approval: **required**",
                    "",
                    str(patch.get("summary") or candidate.get("reason") or "No patch summary available."),
                ]
                with open(summary_path, "a", encoding="utf-8") as handle:
                    handle.write("\n".join(lines) + "\n")
        print(json.dumps({
            "ok": result.get("status") in {"completed", "idle", "blocked"},
            "worker": "ci_patch_generation",
            "model": GEMINI_MODEL,
            "cost_guard_usd": "0",
            "result": result,
        }, default=str, separators=(",", ":")))
        return 0 if result.get("status") in {"completed", "idle", "blocked"} else 1
    except Exception as exc:
        print(json.dumps({
            "ok": False, "worker": "ci_patch_generation",
            "error_type": type(exc).__name__,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
