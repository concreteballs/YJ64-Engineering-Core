import unittest

from scripts.run_ci_event_worker import process_ci_event
from yj64_engineering_core.automation.worker import TaskExecutionResult


class FakeStore:
    def __init__(self, event):
        self.event = event
        self.requested = []

    def get_ci_event(self, event_id):
        self.requested.append(event_id)
        return self.event


class FakeContext:
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

    def test_valid_persisted_event_is_acknowledged(self):
        store = FakeStore(self.valid_event())
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(store),
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(store.requested, [42])

    def test_missing_event_is_blocked(self):
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(None)),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_not_found")

    def test_wrong_repository_is_blocked(self):
        event = self.valid_event()
        event["repository"] = "someone/else"
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(event)),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_scope_rejected")

    def test_malformed_payload_is_blocked(self):
        result = process_ci_event(
            {"payload": {"event_id": True}},
            FakeContext(FakeStore(self.valid_event())),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "invalid_ci_event_id")

    def test_wrong_run_url_is_blocked(self):
        event = self.valid_event()
        event["run_url"] = "https://example.invalid/run"
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            FakeContext(FakeStore(event)),
        )
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "ci_event_integrity_rejected")


if __name__ == "__main__":
    unittest.main()
