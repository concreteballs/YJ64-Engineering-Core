"""Run one deterministic, review-gated CI repair-plan task."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.ci_fix_proposals import process_ci_fix_proposal
from yj64_engineering_core.automation.postgres_store import PostgresCycleStore
from yj64_engineering_core.automation.supabase_storage import SupabaseStorageArtifactStore
from yj64_engineering_core.automation.worker import WorkerRunner


def _write_step_summary(saved: dict) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    proposal = saved.get("proposal_json") or {}
    diagnosis = proposal.get("diagnosis") or {}

    def fenced(value) -> str:
        safe = str(value if value is not None else "").replace("```", "'''")
        return "```text\n" + safe + "\n```"

    lines = [
        "## YJ64 CI repair proposal",
        "",
        f"- Status: `{saved.get('proposal_status', 'unknown')}`",
        f"- Analysis task: `{saved.get('analysis_task_id', 'unknown')}`",
        "- Automatic repository edits: **disabled**",
        "- Human approval: **required**",
        "",
        "### Diagnosis",
        "",
        fenced(diagnosis.get("root_cause", "")),
        "",
        "### Proposed actions",
        "",
    ]
    for action in proposal.get("proposed_actions", []):
        lines.extend([fenced(action), ""])
    lines.extend(["### Verification plan", ""])
    for step in proposal.get("verification_plan", []):
        lines.extend([fenced(step), ""])
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    required = ("YJ64_DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        print(json.dumps({"ok": False, "error": "required_server_secrets_missing", "names": missing}))
        return 2

    run_id = os.environ.get("GITHUB_RUN_ID", "manual")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    worker_id = f"gha-ci-fix-proposal-{run_id}-{run_attempt}"
    try:
        store = PostgresCycleStore(os.environ["YJ64_DATABASE_URL"])
        artifacts = SupabaseStorageArtifactStore.from_environment(
            bucket="yj64-private-artifacts",
            max_upload_bytes=2 * 1024 * 1024,
        )
        runner = WorkerRunner(
            store,
            worker_id=worker_id,
            handlers={
                "prepare_ci_fix": lambda task, context: process_ci_fix_proposal(
                    task, context, artifact_store=artifacts
                )
            },
            lease_seconds=300,
            recovery_limit=100,
            allowed_task_types=["prepare_ci_fix"],
        )
        result = runner.run_once()
        if isinstance(result.get("task_id"), int):
            saved = store.get_ci_fix_proposal(result["task_id"])
            if saved is not None:
                _write_step_summary(saved)
        print(json.dumps({
            "ok": result.get("status") in {"completed", "idle", "blocked"},
            "worker": "ci_fix_proposal",
            "result": result,
        }, default=str, separators=(",", ":")))
        return 0 if result.get("status") in {"completed", "idle", "blocked"} else 1
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "worker": "ci_fix_proposal",
            "error_type": type(exc).__name__,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
