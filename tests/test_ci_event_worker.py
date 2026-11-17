import io
import unittest
import zipfile

from scripts.run_ci_event_worker import process_ci_event
from yj64_engineering_core.automation.worker import TaskExecutionResult


def make_archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("job/step.txt", "pytest: all checks passed")
    return output.getvalue()


class FakeStore:
    def __init__(self, event):
        self.event = event
        self.requested = []
        self.saved = None

    def get_ci_event(self, event_id):
        self.requested.append(event_id)
        return self.event

    def save_payload_manifest(self, task_id, worker_id, manifest, chunks, lease_seconds):
        self.saved = (manifest, chunks)
        return {"persisted": True}

    def assemble_payload_for_model(self, task_id, worker_id, payload_id, **kwargs):
        manifest, _ = self.saved
        return {"ready_for_model": True, "total_sha256": manifest["total_sha256"]}


class FakeContext:
    task_id = 17
    worker_id = "worker"
    lease_seconds = 300

    def __init__(self, store):
        self.store = store


class CiEventWorkerTests(unittest.TestCase):
    def valid_event(self):
        return {
            "event_id": 42,
            "repository": "concreteballs/YJ64-Engineering-Core",
            "run_id": 12345,
            "run_attempt": 1,
            "workflow": "Python tests",
            "conclusion": "success",
            "commit_sha": "a" * 40,
            "branch": "main",
            "run_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/12345",
        }

    def test_valid_persisted_event_fetches_and_persists_logs(self):
        store = FakeStore(self.valid_event())
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(store),
            github_token="token",
            logs_fetcher=lambda *args: make_archive(),
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(store.requested, [42])
        self.assertIsNotNone(store.saved)

    def test_missing_event_is_blocked(self):
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(None)),
            github_token="token",
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_not_found")

    def test_wrong_repository_is_blocked(self):
        event = self.valid_event()
        event["repository"] = "someone/else"
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(event)),
            github_token="token",
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_scope_rejected")

    def test_malformed_payload_is_blocked(self):
        result = process_ci_event(
            {"payload": {"event_id": True}},
            FakeContext(FakeStore(self.valid_event())),
            github_token="token",
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "invalid_ci_event_id")

    def test_wrong_run_url_is_blocked(self):
        event = self.valid_event()
        event["run_url"] = "https://example.invalid/run"
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(event)),
            github_token="token",
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_integrity_rejected")


if __name__ == "__main__":
    unittest.main()
