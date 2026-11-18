import unittest

from yj64_engineering_core.automation.parent_tasks import (
    TaskAdapterRegistry,
    handle_parent_task_request,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult
from yj64_engineering_core.task_contracts import TaskRequest


class FakeContext:
    task_id = 42
    worker_id = "parent-worker"
    lease_seconds = 300

    def __init__(self, checkpoint=None):
        self.checkpoint = checkpoint
        self.store = self

    def load_latest_checkpoint(self):
        return self.checkpoint

    def enqueue_council_task_and_suspend_parent(self, *args, **kwargs):
        return {"enqueued": True}


def request(
    *,
    task_type="code.review",
    capabilities=("github.read",),
    council_policy="optional",
):
    return TaskRequest(
        task_id="repo-review-42",
        task_type=task_type,
        title="Review repository",
        objective="Inspect the supplied repository",
        input_data={"repository": "owner/project"},
        requested_capabilities=capabilities,
        council_policy=council_policy,
    )


def queued(request_value):
    return {
        "task_id": 42,
        "task_type": "execute_task_request",
        "payload": {"task_request": request_value.to_dict()},
    }


class ParentTaskHandlerTests(unittest.TestCase):
    def test_routes_only_to_explicitly_registered_adapter(self):
        registry = TaskAdapterRegistry()
        calls = []
        registry.register(
            "code.review",
            lambda req, state, context: (
                calls.append((req.task_id, state.stage)) or TaskExecutionResult("completed")
            ),
            capabilities=("github.read",),
        )

        result = handle_parent_task_request(
            queued(request()), FakeContext(), registry=registry
        )

        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(calls, [("repo-review-42", "new")])

    def test_rejects_unregistered_task_type(self):
        result = handle_parent_task_request(
            queued(request()), FakeContext(), registry=TaskAdapterRegistry()
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "no_task_adapter_registered"))

    def test_rejects_unregistered_capability(self):
        registry = TaskAdapterRegistry()
        registry.register("code.review", lambda *_: TaskExecutionResult("completed"))
        result = handle_parent_task_request(
            queued(request()), FakeContext(), registry=registry
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "task_capability_not_registered"))

    def test_resumes_from_verified_council_checkpoint(self):
        checkpoint = {
            "task_id": "42",
            "task_state": {
                "stage": "council_result_received",
                "resume_state": {"next_step": "apply_review"},
                "council_resume_event": {
                    "result_artifact_ref": "private://result/42",
                    "result_sha256": "a" * 64,
                },
            },
            "artifact_refs": ["private://result/42"],
        }
        registry = TaskAdapterRegistry()
        seen = []

        def adapter(req, state, context):
            seen.append(state)
            return TaskExecutionResult("completed")

        registry.register("code.review", adapter, capabilities=("github.read",))
        result = handle_parent_task_request(
            queued(request()), FakeContext(checkpoint), registry=registry
        )

        self.assertEqual(result, TaskExecutionResult("completed"))
        self.assertEqual(seen[0].stage, "council_result_received")
        self.assertEqual(seen[0].resume_state, {"next_step": "apply_review"})
        self.assertEqual(seen[0].council_resume_event["result_sha256"], "a" * 64)
        self.assertEqual(seen[0].artifact_refs, ("private://result/42",))

    def test_required_council_must_be_handed_off_before_first_completion(self):
        registry = TaskAdapterRegistry()
        registry.register(
            "code.review",
            lambda *_: TaskExecutionResult("completed"),
            capabilities=("github.read",),
            council_enabled=True,
        )
        result = handle_parent_task_request(
            queued(request(council_policy="required")),
            FakeContext(),
            registry=registry,
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "required_council_handoff_missing"))

    def test_required_council_accepts_suspended_handoff(self):
        registry = TaskAdapterRegistry()
        registry.register(
            "code.review",
            lambda *_: TaskExecutionResult("suspended", "waiting_for_council"),
            capabilities=("github.read",),
            council_enabled=True,
        )
        result = handle_parent_task_request(
            queued(request(council_policy="required")),
            FakeContext(),
            registry=registry,
        )
        self.assertEqual(result, TaskExecutionResult("suspended", "waiting_for_council"))

    def test_never_policy_blocks_council_store_operation(self):
        registry = TaskAdapterRegistry()

        def adapter(req, state, context):
            context.store.enqueue_council_task_and_suspend_parent()
            return TaskExecutionResult("completed")

        registry.register("code.review", adapter, capabilities=("github.read",), council_enabled=True)
        result = handle_parent_task_request(
            queued(request(council_policy="never")),
            FakeContext(),
            registry=registry,
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "council_use_forbidden"))

    def test_rejects_waiting_checkpoint_without_resume_event(self):
        checkpoint = {
            "task_id": "42",
            "task_state": {"stage": "waiting_council", "resume_state": {}},
            "artifact_refs": [],
        }
        registry = TaskAdapterRegistry()
        registry.register("code.review", lambda *_: TaskExecutionResult("completed"), capabilities=("github.read",))
        result = handle_parent_task_request(
            queued(request()), FakeContext(checkpoint), registry=registry
        )
        self.assertEqual(result, TaskExecutionResult("blocked", "invalid_parent_task_request"))

    def test_duplicate_adapter_registration_is_rejected(self):
        registry = TaskAdapterRegistry()
        registry.register("code.review", lambda *_: TaskExecutionResult("completed"))
        with self.assertRaises(ValueError):
            registry.register("code.review", lambda *_: TaskExecutionResult("completed"))


if __name__ == "__main__":
    unittest.main()
