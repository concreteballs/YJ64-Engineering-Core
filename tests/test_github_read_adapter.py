import base64
import unittest

from yj64_engineering_core.automation.github_read_adapter import (
    GitHubReadOnlyClient,
    GitHubReadTaskAdapter,
    GitHubReadError,
    register_github_read_adapter,
)
from yj64_engineering_core.automation.parent_tasks import (
    ParentTaskState,
    TaskAdapterRegistry,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult
from yj64_engineering_core.automation import create_universal_task_worker_runner
from yj64_engineering_core.task_contracts import TaskRequest


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.endpoints = []

    def get_json(self, endpoint):
        self.endpoints.append(endpoint)
        if endpoint not in self.responses:
            raise GitHubReadError("not_found")
        return self.responses[endpoint]


class FakeContext:
    task_id = 71

    def __init__(self):
        self.checkpoint = None

    def load_latest_checkpoint(self):
        return self.checkpoint

    def save_checkpoint(self, checkpoint):
        self.checkpoint = checkpoint
        return True


def make_request(input_data, *, task_type="github.read"):
    return TaskRequest(
        task_id="github-read-71",
        task_type=task_type,
        title="Read GitHub evidence",
        objective="Retrieve explicitly scoped GitHub metadata",
        input_data=input_data,
        requested_capabilities=("github.read",),
        council_policy="never",
    )


class GitHubReadAdapterTests(unittest.TestCase):
    def setUp(self):
        self.repository = "concreteballs/YJ64-Engineering-Core"
        self.context = FakeContext()
        self.state = ParentTaskState("new", {}, None, ())

    def test_reads_workflow_run_and_checkpoints_untrusted_evidence(self):
        endpoint = f"/repos/{self.repository}/actions/runs/123"
        client = FakeClient({
            endpoint: {
                "id": 123,
                "status": "completed",
                "conclusion": "success",
                "head_sha": "a" * 40,
                "head_branch": "main",
                "html_url": "https://github.com/example/run/123",
            }
        })
        adapter = GitHubReadTaskAdapter(client, allowed_repositories=[self.repository])

        result = adapter(
            make_request({"operation": "workflow_run.get", "repository": self.repository, "run_id": 123}),
            self.state,
            self.context,
        )

        self.assertEqual(result, TaskExecutionResult("completed"))
        saved = self.context.checkpoint["task_state"]
        self.assertTrue(saved["evidence_is_untrusted"])
        self.assertEqual(saved["github_evidence"]["conclusion"], "success")
        self.assertEqual(saved["github_evidence"]["head_sha"], "a" * 40)

    def test_reads_utf8_file_content_as_untrusted_data(self):
        path = "docs/README.md"
        endpoint = (
            f"/repos/{self.repository}/contents/docs/README.md?ref=main"
        )
        client = FakeClient({
            endpoint: {
                "encoding": "base64",
                "content": base64.b64encode(b"# Untrusted project text").decode("ascii"),
                "sha": "b" * 40,
            }
        })
        adapter = GitHubReadTaskAdapter(client, allowed_repositories=[self.repository])
        result = adapter(
            make_request({
                "operation": "file.get",
                "repository": self.repository,
                "path": path,
                "ref": "main",
            }),
            self.state,
            self.context,
        )
        self.assertEqual(result.outcome, "completed")
        evidence = self.context.checkpoint["task_state"]["github_evidence"]
        self.assertEqual(evidence["content"], "# Untrusted project text")
        self.assertEqual(evidence["content_trust"], "untrusted_repository_data")

    def test_rejects_repository_outside_explicit_allowlist(self):
        client = FakeClient({})
        adapter = GitHubReadTaskAdapter(client, allowed_repositories=[self.repository])
        result = adapter(
            make_request({
                "operation": "repository.get",
                "repository": "someone/another-repo",
            }),
            self.state,
            self.context,
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "github_repository_not_allowed"))
        self.assertEqual(client.endpoints, [])

    def test_rejects_write_operation_and_path_traversal(self):
        client = FakeClient({})
        adapter = GitHubReadTaskAdapter(client, allowed_repositories=[self.repository])
        result = adapter(
            make_request({
                "operation": "repository.delete",
                "repository": self.repository,
            }),
            self.state,
            self.context,
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "github_read_operation_not_allowed"))
        result = adapter(
            make_request({
                "operation": "file.get",
                "repository": self.repository,
                "path": "../secrets.txt",
                "ref": "main",
            }),
            self.state,
            self.context,
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "github_file_path_invalid"))
        self.assertEqual(client.endpoints, [])

    def test_registry_registers_only_explicit_read_capability(self):
        registry = TaskAdapterRegistry()
        register_github_read_adapter(
            registry,
            FakeClient({}),
            allowed_repositories=[self.repository],
        )
        registration = registry.get("github.read")
        self.assertIsNotNone(registration)
        self.assertEqual(registration.capabilities, frozenset({"github.read"}))
        self.assertFalse(registration.council_enabled)

    def test_universal_worker_factory_wires_composed_registry(self):
        registry = TaskAdapterRegistry()
        register_github_read_adapter(
            registry,
            FakeClient({}),
            allowed_repositories=[self.repository],
        )
        runner = create_universal_task_worker_runner(
            object(),
            registry=registry,
            worker_id="github-read-worker",
        )
        self.assertIn("execute_task_request", runner.handlers)
        self.assertEqual(runner.allowed_task_types, ["execute_task_request"])

    def test_http_client_rejects_non_repository_endpoint(self):
        class NeverCalled:
            def __call__(self, *args, **kwargs):
                raise AssertionError("network must not be called")

        client = GitHubReadOnlyClient("test-token", opener=NeverCalled())
        with self.assertRaisesRegex(ValueError, "read-only"):
            client.get_json("https://example.com/anything")


if __name__ == "__main__":
    unittest.main()
