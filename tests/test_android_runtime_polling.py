import json
import unittest
from datetime import datetime, timezone

from scripts.poll_android_runtime_runs import (
    APP_REPOSITORY, WORKFLOW_PATH, build_event, fetch_recent_events, poll_and_persist,
)


def valid_run():
    return {
        "id": 123, "run_attempt": 2, "path": WORKFLOW_PATH,
        "event": "push", "head_branch": "main", "status": "completed",
        "conclusion": "failure", "head_sha": "a" * 40,
        "html_url": f"https://github.com/{APP_REPOSITORY}/actions/runs/123",
    }


class FakeResponse:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body[:limit]


class FakeStore:
    def __init__(self): self.events = []
    def record_ci_event(self, event):
        self.events.append(event)
        return {"accepted": True, "duplicate": False, "task_enqueued": True}


class AndroidRuntimePollingTests(unittest.TestCase):
    def test_builds_scoped_event(self):
        event = build_event(valid_run())
        self.assertEqual(event["repository"], APP_REPOSITORY)
        self.assertEqual(event["workflow"], WORKFLOW_PATH)
        self.assertEqual(event["run_attempt"], 2)

    def test_rejects_wrong_workflow_and_unfinished_run(self):
        run = valid_run()
        run["path"] = ".github/workflows/other.yml"
        self.assertIsNone(build_event(run))
        run = valid_run()
        run["status"] = "in_progress"
        self.assertIsNone(build_event(run))

    def test_fetch_and_persist(self):
        payload = {"workflow_runs": [valid_run()]}
        urls = []
        def opener(request, timeout):
            urls.append(request.full_url)
            return FakeResponse(json.dumps(payload).encode())
        now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(len(fetch_recent_events(opener=opener, now=now)), 1)
        self.assertIn("android-build.yml/runs", urls[0])
        store = FakeStore()
        result = poll_and_persist(store, opener=opener, now=now)
        self.assertEqual(result["events_accepted"], 1)
        self.assertEqual(len(store.events), 1)


if __name__ == "__main__":
    unittest.main()
