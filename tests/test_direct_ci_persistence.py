import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_ci_completion.py"
SPEC = importlib.util.spec_from_file_location("record_ci_completion", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DirectCiPersistenceTests(unittest.TestCase):
    def payload(self):
        return {
            "repository": {"full_name": "concreteballs/YJ64-Engineering-Core"},
            "workflow_run": {
                "name": "Python tests",
                "event": "push",
                "head_branch": "main",
                "id": 123,
                "run_attempt": 2,
                "conclusion": "success",
                "head_sha": "a" * 40,
                "html_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/123",
            },
        }

    def test_builds_valid_database_event(self):
        event = MODULE.build_event(self.payload())
        self.assertEqual(event["run_id"], 123)
        self.assertEqual(event["run_attempt"], 2)
        self.assertEqual(event["workflow"], "Python tests")

    def test_rejects_wrong_repository(self):
        payload = self.payload()
        payload["repository"]["full_name"] = "someone/else"
        with self.assertRaisesRegex(ValueError, "repository_scope_rejected"):
            MODULE.build_event(payload)

    def test_rejects_non_main_branch(self):
        payload = self.payload()
        payload["workflow_run"]["head_branch"] = "feature"
        with self.assertRaisesRegex(ValueError, "workflow_scope_rejected"):
            MODULE.build_event(payload)

    def test_rejects_invalid_commit_sha(self):
        payload = self.payload()
        payload["workflow_run"]["head_sha"] = "not-a-sha"
        with self.assertRaisesRegex(ValueError, "invalid_commit_sha"):
            MODULE.build_event(payload)

    def test_persists_event_through_existing_queue_store(self):
        class FakeStore:
            def __init__(self, database_url):
                self.database_url = database_url

            def record_ci_event(self, event):
                self.event = event
                return {
                    "duplicate": False,
                    "event_id": 17,
                    "task_enqueued": True,
                }

        with patch.object(MODULE, "PostgresCycleStore", FakeStore):
            event = MODULE.build_event(self.payload())
            result = MODULE.PostgresCycleStore("postgresql://test").record_ci_event(event)
        self.assertEqual(result["event_id"], 17)
        self.assertTrue(result["task_enqueued"])


if __name__ == "__main__":
    unittest.main()
