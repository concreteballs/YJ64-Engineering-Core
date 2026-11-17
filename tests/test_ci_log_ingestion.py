import io
import unittest
import zipfile
from hashlib import sha256

from scripts.run_ci_event_worker import process_ci_event
from yj64_engineering_core.automation.ci_log_ingestion import (
    GitHubLogsError,
    extract_text_logs,
    fetch_run_logs,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult


def make_archive(name="worker/test.txt", content="build failed"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return output.getvalue()


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


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
        return {"persisted": True, "payload_id": manifest["payload_id"]}

    def assemble_payload_for_model(
        self, task_id, worker_id, payload_id,
        require_acknowledgements=False, lease_seconds=300,
    ):
        manifest, chunks = self.saved
        self.asserted_payload_id = payload_id
        return {
            "ready_for_model": True,
            "payload_id": payload_id,
            "total_sha256": manifest["total_sha256"],
        }


class FakeContext:
    task_id = 17
    worker_id = "test-worker"
    lease_seconds = 300

    def __init__(self, store):
        self.store = store


class CiLogIngestionTests(unittest.TestCase):
    def test_extracts_text_and_redacts_credentials(self):
        archive = make_archive(
            content="Authorization: Bearer token-secret-123\n"
                    "key=AIza123456789012345678901234567890"
        )
        text = extract_text_logs(archive, secrets=("token-secret-123",))
        self.assertIn("[REDACTED]", text)
        self.assertIn("[REDACTED_GOOGLE_KEY]", text)
        self.assertNotIn("token-secret-123", text)

    def test_rejects_archive_path_traversal(self):
        with self.assertRaises(GitHubLogsError) as caught:
            extract_text_logs(make_archive("../escape.txt", "x"))
        self.assertEqual(caught.exception.classification, "unsafe_log_archive_path")
        self.assertFalse(caught.exception.retryable)

    def test_rejects_logs_over_size_limit(self):
        with self.assertRaises(GitHubLogsError) as caught:
            extract_text_logs(make_archive(content="12345"), max_log_bytes=4)
        self.assertEqual(caught.exception.classification, "run_logs_exceed_storage_limit")

    def test_fetches_exact_attempt_with_read_only_request(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return FakeResponse(b"zip-data")

        result = fetch_run_logs(
            "concreteballs/YJ64-Engineering-Core", 12345, 2, "test-token",
            opener=opener,
        )
        self.assertEqual(result, b"zip-data")
        self.assertTrue(captured["url"].endswith("/runs/12345/attempts/2/logs"))
        self.assertEqual(captured["authorization"], "Bearer test-token")

    def test_rejects_other_repository(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            fetch_run_logs("someone/else", 1, 1, "token", opener=lambda *a, **k: None)

    def test_valid_ci_event_persists_verified_log_payload(self):
        event = {
            "event_id": 42,
            "repository": "concreteballs/YJ64-Engineering-Core",
            "run_id": 12345,
            "run_attempt": 1,
            "workflow": "Python tests",
            "conclusion": "failure",
            "commit_sha": "a" * 40,
            "branch": "main",
            "run_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/12345",
        }
        store = FakeStore(event)
        context = FakeContext(store)
        result = process_ci_event(
            {"payload": {"event_id": 42}},
            context,
            github_token="secret-token",
            logs_fetcher=lambda *args: make_archive(content="failure secret-token"),
        )
        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(store.requested, [42])
        manifest, chunks = store.saved
        combined = "".join(item["content"] for item in chunks)
        self.assertIn("run_id: 12345", combined)
        self.assertIn("[REDACTED]", combined)
        self.assertNotIn("secret-token", combined)
        self.assertEqual(manifest["source_refs"][0], event["run_url"])

    def test_missing_github_token_blocks_before_network(self):
        event = {
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
        called = []
        result = process_ci_event(
            {"payload": {"event_id": 42}}, FakeContext(FakeStore(event)),
            github_token="", logs_fetcher=lambda *args: called.append(args),
        )
        self.assertEqual(result.reason, "github_token_not_configured")
        self.assertEqual(called, [])

    def test_transient_log_fetch_failure_is_retried(self):
        event = {
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

        def unavailable(*args):
            raise GitHubLogsError("github_logs_http_404", retryable=True)

        result = process_ci_event(
            {"payload": {"event_id": 42}}, FakeContext(FakeStore(event)),
            github_token="token", logs_fetcher=unavailable,
        )
        self.assertEqual(result, TaskExecutionResult("retry", "github_logs_http_404", 90))


if __name__ == "__main__":
    unittest.main()
