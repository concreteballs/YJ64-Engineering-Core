"""Run one budget-gated CI patch task and publish safe candidates for human review."""
from __future__ import annotations

import json
import os
import subprocess
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


EXPECTED_REPOSITORY = "concreteballs/YJ64-Engineering-Core"


def _git(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args], input=input_text, text=True, capture_output=True,
        check=False, timeout=120,
    )
    if result.returncode:
        raise RuntimeError("patch_review_git_operation_failed")
    return result.stdout.strip()


def publish_candidate_for_review(candidate: dict, *, repository: str, token: str) -> str:
    """Publish a validated diff on an isolated branch and open a draft PR."""
    if repository != EXPECTED_REPOSITORY:
        raise ValueError("patch_review_repository_rejected")
    if not token.strip():
        raise ValueError("github_token_missing")
    safety = candidate.get("safety") or {}
    patch = candidate.get("patch") or {}
    source = candidate.get("source") or {}
    if (
        candidate.get("candidate_status") != "awaiting_review"
        or safety.get("git_apply_check") is not True
        or safety.get("human_approval_required") is not True
        or safety.get("auto_apply") is not False
        or safety.get("auto_commit") is not False
    ):
        raise ValueError("candidate_not_eligible_for_human_review")
    diff = patch.get("unified_diff")
    files = patch.get("target_files")
    base_sha = source.get("current_head_sha")
    proposal_id = candidate.get("proposal_task_id")
    digest = candidate.get("candidate_sha256")
    if (
        not isinstance(diff, str) or not diff.strip()
        or not isinstance(files, list) or not files
        or any(not isinstance(p, str) or p.startswith("/") or ".." in p.split("/") for p in files)
        or not isinstance(base_sha, str) or len(base_sha) != 40
        or not isinstance(proposal_id, int) or isinstance(proposal_id, bool)
        or not isinstance(digest, str) or len(digest) != 64
    ):
        raise ValueError("patch_review_candidate_invalid")

    branch = f"ci-patch/review-{proposal_id}-{digest[:10]}"
    env = {**os.environ, "GH_TOKEN": token}
    _git(["fetch", "--quiet", "origin", "main"])
    remote_main = _git(["ls-remote", "origin", "refs/heads/main"]).split()[0]
    if remote_main != base_sha:
        raise RuntimeError("patch_base_is_no_longer_current_main")

    existing = subprocess.run(
        ["gh", "pr", "list", "--repo", repository, "--head", branch,
         "--json", "url", "--jq", ".[0].url"],
        text=True, capture_output=True, check=False, env=env, timeout=60,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        return existing.stdout.strip()
    if _git(["ls-remote", "--heads", "origin", f"refs/heads/{branch}"]):
        raise RuntimeError("patch_review_branch_exists_without_matching_pull_request")

    _git(["checkout", "--quiet", "--detach", base_sha])
    _git(["switch", "--quiet", "-c", branch])
    _git(["apply", "--check", "--whitespace=error", "-"], input_text=diff)
    _git(["apply", "--whitespace=error", "-"], input_text=diff)
    _git(["add", "--", *files])
    staged = _git(["diff", "--cached", "--name-only"]).splitlines()
    if sorted(staged) != sorted(set(files)):
        raise RuntimeError("patch_review_staged_file_set_mismatch")
    _git(["diff", "--cached", "--check"])
    _git(["config", "user.name", "github-actions[bot]"])
    _git(["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    _git(["commit", "-m", f"Propose CI patch for proposal {proposal_id}"])
    _git(["push", "origin", branch])

    summary = str(patch.get("summary") or "Automated CI patch candidate").replace("\n", " ")[:180]
    steps = patch.get("verification_steps") or []
    body = "\n".join([
        "## Human review required",
        "",
        "This draft contains an AI-prepared patch. It has not been applied to main.",
        "Review every changed line and the checks before marking this PR ready.",
        "",
        f"- Proposal task: {proposal_id}",
        f"- Candidate SHA-256: {digest}",
        f"- Failed source commit: {source.get('commit_sha', 'unknown')}",
        f"- Patch base (main): {base_sha}",
        f"- Model confidence: {patch.get('confidence', 'not supplied')}",
        "",
        "### Patch summary",
        summary,
        "",
        "### Suggested verification",
        *[f"- {str(step)[:500]}" for step in steps[:12]],
        "",
        "The patch was checked with git apply --check against the exact base commit. "
        "This is not proof of correctness. CI and human review are still required.",
    ])
    created = subprocess.run(
        ["gh", "pr", "create", "--repo", repository, "--draft",
         "--base", "main", "--head", branch,
         "--title", f"[CI patch] {summary[:100]}", "--body", body],
        text=True, capture_output=True, check=False, env=env, timeout=90,
    )
    if created.returncode:
        raise RuntimeError("patch_review_pull_request_creation_failed")
    pr_url = created.stdout.strip()
    dispatched = subprocess.run(
        ["gh", "workflow", "run", "tests.yml", "--repo", repository, "--ref", branch],
        text=True, capture_output=True, check=False, env=env, timeout=60,
    )
    if dispatched.returncode:
        print(json.dumps({"warning": "review_pr_created_but_ci_dispatch_failed"}))
    return pr_url


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
        pr_url = None
        if saved is not None:
            candidate = saved.get("candidate_json") or {}
            if saved.get("candidate_status") == "awaiting_review":
                pr_url = publish_candidate_for_review(
                    {**candidate, "candidate_sha256": saved.get("candidate_sha256")},
                    repository=os.environ.get("GITHUB_REPOSITORY", EXPECTED_REPOSITORY),
                    token=os.environ.get("GITHUB_TOKEN", ""),
                )
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
            if summary_path:
                lines = [
                    "## YJ64 CI patch candidate",
                    "",
                    f"- Status: {saved.get('candidate_status')}",
                    f"- Proposal task: {saved.get('proposal_task_id')}",
                    f"- Source commit: {(candidate.get('source') or {}).get('commit_sha', 'unknown')}",
                    f"- Current HEAD: {(candidate.get('source') or {}).get('current_head_sha', 'not inspected')}",
                    "- Automatic apply to main: **disabled**",
                    "- Human approval: **required**",
                ]
                if pr_url:
                    lines.extend(["", f"- Draft review PR: {pr_url}"])
                patch = candidate.get("patch") or {}
                lines.extend(["", str(patch.get("summary") or candidate.get("reason") or "No patch summary available.")])
                with open(summary_path, "a", encoding="utf-8") as handle:
                    handle.write("\n".join(lines) + "\n")
        print(json.dumps({
            "ok": result.get("status") in {"completed", "idle", "blocked"},
            "worker": "ci_patch_generation",
            "model": GEMINI_MODEL,
            "cost_guard_usd": "0",
            "review_pr": pr_url,
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
