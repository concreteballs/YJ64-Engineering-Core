import unittest

from yj64_engineering_core.automation.checkpoints import verify_checkpoint
from yj64_engineering_core.automation.cross_module_tasks import (
    PROTOCOL_VERSION, TASK_TYPE, create_cross_module_task_handler,
)
from yj64_engineering_core.automation.worker import TaskExecutionResult
from yj64_engineering_core.extensions import (
    ExtensionCapability, ExtensionManifest, ExtensionRegistry,
)


CANDIDATE = {
    "schema_id": "yj64.cross_module.candidate.v1",
    "schema_version": "1.0",
    "candidate_id": "candidate-42",
    "version": 3,
    "candidate_schema_version": "1.0",
    "origin_module": "biology",
}


class FakeContext:
    task_id = 91

    def __init__(self):
        self.checkpoint = None
        self.saved = []

    def load_latest_checkpoint(self):
        return self.checkpoint

    def save_checkpoint(self, checkpoint):
        verify_checkpoint(checkpoint)
        self.checkpoint = checkpoint
        self.saved.append(checkpoint)
        return True


class FakeAdapter:
    def __init__(self, module_id, version):
        self.module_id = module_id
        self.version = version
        self.review_calls = 0
        self.contribution_calls = 0

    def review_candidate(self, candidate):
        self.review_calls += 1
        return {
            "schema_id": "yj64.cross_module.review.v1",
            "schema_version": "1.0",
            "candidate": candidate,
            "reviewer_module": self.module_id,
            "reviewer_version": self.version,
            "status": "pass",
            "rationale": "Independent review completed",
        }

    def contribute_enhancements(self, candidate):
        self.contribution_calls += 1
        return {
            "schema_id": "yj64.cross_module.contribution.v1",
            "schema_version": "1.0",
            "candidate": candidate,
            "module_id": self.module_id,
            "proposals": [],
            "no_proposal": True,
            "rationale": "No evidence-backed improvement identified",
        }


def make_registry():
    registry = ExtensionRegistry()
    for extension_id, name in (
        ("yj64.biological-engineering", "Biological"),
        ("yj64.materials", "Materials"),
    ):
        registry.register(ExtensionManifest(
            extension_id=extension_id,
            name=name,
            version="0.1.0",
            kind="discipline_pack",
            capabilities=(
                ExtensionCapability(
                    "review_candidate", "yj64.cross_module.candidate.v1",
                    "yj64.cross_module.review.v1",
                ),
                ExtensionCapability(
                    "contribute_enhancements", "yj64.cross_module.candidate.v1",
                    "yj64.cross_module.contribution.v1",
                ),
            ),
            permissions=(),
            safety_class="test_only",
            offline_supported=True,
        ))
    return registry


class CrossModuleTaskHandlerTests(unittest.TestCase):
    def setUp(self):
        self.registry = make_registry()
        self.bindings = {
            "biology": "yj64.biological-engineering",
            "materials": "yj64.materials",
        }
        self.adapters = {
            extension_id: FakeAdapter(module, "0.1.0")
            for module, extension_id in self.bindings.items()
        }
        self.handler = create_cross_module_task_handler(
            registry=self.registry,
            module_bindings=self.bindings,
            adapters=self.adapters,
        )
        self.task = {
            "task_id": 91,
            "task_type": TASK_TYPE,
            "payload": {
                "protocol_version": PROTOCOL_VERSION,
                "candidate": CANDIDATE,
                "relevant_modules": ["biology", "materials"],
            },
        }
        self.context = FakeContext()

    def test_runs_inside_worker_handler_contract_and_persists_assessment(self):
        result = self.handler(self.task, self.context)
        self.assertEqual(result, TaskExecutionResult("completed"))
        state = self.context.checkpoint["task_state"]
        self.assertEqual(state["stage"], "cross_module_assessment_ready")
        self.assertEqual(state["assessment"]["decision"], "accepted")
        self.assertEqual(len(state["module_outputs"]), 2)
        self.assertGreaterEqual(len(self.context.saved), 5)

    def test_checkpoint_resume_does_not_repeat_completed_module_calls(self):
        self.handler(self.task, self.context)
        counts = {
            key: (adapter.review_calls, adapter.contribution_calls)
            for key, adapter in self.adapters.items()
        }
        self.handler(self.task, self.context)
        self.assertEqual(counts, {
            key: (adapter.review_calls, adapter.contribution_calls)
            for key, adapter in self.adapters.items()
        })

    def test_wrong_reviewer_identity_is_blocked(self):
        adapter = self.adapters["yj64.materials"]
        adapter.module_id = "biology"
        result = self.handler(self.task, self.context)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "cross_module_review_identity_mismatch")

    def test_unregistered_extension_is_blocked(self):
        task = dict(self.task)
        task["payload"] = dict(self.task["payload"], relevant_modules=["biology", "unknown"])
        result = self.handler(task, self.context)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "cross_module_binding_missing")

    def test_missing_adapter_is_blocked(self):
        handler = create_cross_module_task_handler(
            registry=self.registry,
            module_bindings=self.bindings,
            adapters={"yj64.biological-engineering": self.adapters["yj64.biological-engineering"]},
        )
        result = handler(self.task, self.context)
        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.reason, "cross_module_adapter_unavailable")


if __name__ == "__main__":
    unittest.main()
