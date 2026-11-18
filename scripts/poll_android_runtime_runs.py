"""Poll the public Android client repository for completed emulator-test runs."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore

APP_REPOSITORY = "concreteballs/yj64-clean-bial2modFun5"
WORKFLOW_FILE = "android-build.yml"
WORKFLOW_PATH = ".github/workflows/android-build.yml"
BRANCH = "main"
VALID_CONCLUSIONS = {"success", "failure", "cancelled", "timed_out", "action_required", "neutral", "skipped", "stale"}
MAX_PAGES = 10
PER_PAGE = 100


def _github_request(url: str, *, opener=None, timeout_seconds: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YJ64-Engineering-Core-Android-Runtime-Poller",
    }, method="GET")
    send = opener or urllib.request.urlopen
    try:
        with send(request, timeout=timeout_seconds) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError("github_api_http_error")
            body = response.read(2 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("github_api_http_" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("github_api_transport_error") from None
    if not isinstance(body, bytes) or len(body) > 2 * 1024 * 1024:
        raise RuntimeError("github_api_response_too_large")
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RuntimeError("github_api_invalid_json") from None
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise RuntimeError("github_api_invalid_runs_response")
    return data


def build_event(run: dict) -> dict | None:
    if not isinstance(run, dict) or (
        run.get("path") != WORKFLOW_PATH
        or run.get("event") != "push"
        or run.get("head_branch") != BRANCH
        or run.get("status") != "completed"
        or run.get("conclusion") not in VALID_CONCLUSIONS
    ):
        return None
    run_id, attempt, sha = run.get("id"), run.get("run_attempt"), run.get("head_sha")
    if (
        not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1
        or not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1
        or not isinstance(sha, str) or len(sha) != 40
        or any(char not in "0123456789abcdef" for char in sha)
    ):
        return None
    run_url = run.get("html_url")
    if run_url != f"https://github.com/{APP_REPOSITORY}/actions/runs/{run_id}":
        return None
    return {
        "repository": APP_REPOSITORY, "run_id": run_id, "run_attempt": attempt,
        "workflow": WORKFLOW_PATH, "conclusion": run["conclusion"],
        "commit_sha": sha, "branch": BRANCH, "run_url": run_url,
    }


def fetch_recent_events(*, opener=None, now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    start_date = (current - timedelta(days=30)).date().isoformat()
    end_date = current.date().isoformat()
    events = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode({
            "branch": BRANCH, "event": "push",
            "created": f"{start_date}..{end_date}",
            "per_page": PER_PAGE, "page": page,
        })
        url = f"https://api.github.com/repos/{APP_REPOSITORY}/actions/workflows/{WORKFLOW_FILE}/runs?{query}"
        runs = _github_request(url, opener=opener)["workflow_runs"]
        for run in reversed(runs):
            event = build_event(run)
            if event is not None:
                events.append(event)
        if len(runs) < PER_PAGE:
            return events
    raise RuntimeError("android_runtime_run_poll_page_limit_reached")


def poll_and_persist(store, *, opener=None, now: datetime | None = None) -> dict:
    events = fetch_recent_events(opener=opener, now=now)
    accepted = duplicates = 0
    for event in events:
        result = store.record_ci_event(event)
        if result.get("duplicate"):
            duplicates += 1
        elif result.get("accepted") and result.get("task_enqueued"):
            accepted += 1
        else:
            raise RuntimeError("android_runtime_event_persistence_incomplete")
    return {"runs_found": len(events), "events_accepted": accepted,
            "duplicates": duplicates, "repository": APP_REPOSITORY,
            "workflow": WORKFLOW_PATH}


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    if not database_url:
        print("YJ64_DATABASE_URL is not configured.", file=sys.stderr)
        return 2
    try:
        result = poll_and_persist(PostgresCycleStore(database_url))
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__,
                          "reason": str(exc)[:120]}), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
