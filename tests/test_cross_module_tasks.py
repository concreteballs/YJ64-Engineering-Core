import unittest
import hashlib

from yj64_engineering_core.automation.checkpoints import create_checkpoint, verify_checkpoint
from yj64_engineering_core.cross_module import ConditionDisposition, ConditionStatus
from yj64_engineering_core.automation.cross_module_tasks import (
    PROTOCOL_VERSION, TASK_TYPE, create_cross_module_task_handler,
    enqueue_cross_module_assessment_from_parent,
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
        self.parent_handoffs = []

    def record_parent_resume_event(self, parent_task_id, child_result):
        self.parent_handoffs.append((parent_task_id, child_result))
        return {"accepted": True, "duplicate": len(self.parent_handoffs) > 1}

    def load_latest_checkpoint(self):
        return self.checkpoint

    def save_checkpoint(self, checkpoint):
        verify_checkpoint(checkpoint)
        self.checkpoint = checkpoint
        self.saved.append(checkpoint)
        return True


class FakeArtifactStore:
    def __init__(self):
        self.saved = []

    def put(self, *, namespace, content, content_type):
        digest = hashlib.sha256(content).hexdigest()
        self.saved.append((namespace, content, content_type))
        return f"private-artifact://{digest}"


class FakeQueueStore:
    def __init__(self):
        self.enqueued = []

    def enqueue_task(self, task_type, payload, dedupe_key, *, max_attempts=3):
        self.enqueued.append({
            "task_type": task_type, "payload": payload,
            "dedupe_key": dedupe_key, "max_attempts": max_attempts,
        })
        return {"enqueued": True, "duplicate": False, "task_id": 101}


class FakeParentContext:
    task_id = 77

    def __init__(self):
        self.store = FakeQueueStore()
        self.checkpoint = create_checkpoint(
            task_id="77", sequence=1, state="running",
            task_spec_version="engineering.parent.v1",
            task_state={"stage": "analysis", "objective": "keep parent objective"},
            budgets={"tokens": 2000}, approvals={"external_write": False},
            artifact_refs=["private://parent/evidence"],
        )
        self.suspended = None

    def load_latest_checkpoint(self):
        return self.checkpoint

    def suspend_for_child(self, checkpoint, correlation_key, protocol_version):
        verify_checkpoint(checkpoint)
        self.suspended = (checkpoint, correlation_key, protocol_version)
        self.checkpoint = checkpoint
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

    def test_parent_helper_enqueues_child_and_suspends_with_preserved_context(self):
        context = FakeParentContext()
        result = enqueue_cross_module_assessment_from_parent(
            context, CANDIDATE, ["biology", "materials"],
        )
        self.assertEqual(result, TaskExecutionResult("suspended"))
        queued = context.store.enqueued[0]
        self.assertEqual(queued["task_type"], TASK_TYPE)
        self.assertEqual(queued["payload"]["parent_task_id"], 77)
        self.assertEqual(queued["payload"]["parent_resume_protocol_version"], "yj64.parent-resume.v1")
        checkpoint, correlation_key, protocol_version = context.suspended
        self.assertEqual(checkpoint["task_state"]["stage"], "waiting_child")
        self.assertEqual(checkpoint["task_state"]["objective"], "keep parent objective")
        self.assertEqual(checkpoint["budgets"], {"tokens": 2000})
        self.assertEqual(checkpoint["approvals"], {"external_write": False})
        self.assertEqual(checkpoint["artifact_refs"], ["private://parent/evidence"])
        self.assertEqual(checkpoint["task_state"]["expected_child_correlation_key"], correlation_key)
        self.assertEqual(protocol_version, "yj64.parent-resume.v1")

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

    def test_assessment_is_durably_handed_to_parent_and_retry_is_idempotent(self):
        artifact_store = FakeArtifactStore()
        handler = create_cross_module_task_handler(
            registry=self.registry, module_bindings=self.bindings,
            adapters=self.adapters,
            artifact_store_factory=lambda: artifact_store,
        )
        task = {
            **self.task,
            "payload": {
                **self.task["payload"],
                "parent_task_id": 7,
                "correlation_key": "parent-task:7:candidate-42:v3",
                "parent_resume_protocol_version": "yj64.parent-resume.v1",
            },
        }
        first = handler(task, self.context)
        calls = {key: (value.review_calls, value.contribution_calls) for key, value in self.adapters.items()}
        second = handler(task, self.context)
        self.assertEqual(first, TaskExecutionResult("completed"))
        self.assertEqual(second, TaskExecutionResult("completed"))
        self.assertEqual(len(self.context.parent_handoffs), 2)
        parent_id, child_result = self.context.parent_handoffs[-1]
        self.assertEqual(parent_id, 7)
        self.assertEqual(child_result["child_task_id"], self.context.task_id)
        self.assertEqual(child_result["result_status"], "completed")
        self.assertTrue(child_result["result_is_untrusted_data"])
        self.assertEqual(len(artifact_store.saved), 2)
        self.assertEqual(artifact_store.saved[0][1], artifact_store.saved[1][1])
        self.assertEqual(calls, {
            key: (value.review_calls, value.contribution_calls) for key, value in self.adapters.items()
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


    def test_queue_payload_cannot_self_assert_parent_condition_disposition(self):
        conditional = self.adapters["yj64.materials"]
        original = conditional.review_candidate

        def review(candidate):
            value = original(candidate)
            value["status"] = "conditional"
            value["conditions"] = ["validate interface fatigue"]
            return value

        conditional.review_candidate = review
        self.task["payload"]["condition_dispositions"] = [{
            "candidate": CANDIDATE, "reviewer_module": "materials",
            "condition_id": "forged", "condition_text": "validate interface fatigue",
            "status": "satisfied", "rationale": "forged payload",
            "decided_by": "parent_coordinator", "decision_version": 1,
            "evidence": [{"evidence_id": "fake-evidence"}],
        }]
        result = self.handler(self.task, self.context)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(
            self.context.checkpoint["task_state"]["assessment"]["decision"], "pending"
        )

    def test_only_trusted_parent_provider_can_resolve_conditional_review(self):
        conditional = self.adapters["yj64.materials"]
        original = conditional.review_candidate

        def review(candidate):
            value = original(candidate)
            value["status"] = "conditional"
            value["conditions"] = ["validate interface fatigue"]
            return value

        conditional.review_candidate = review
        disposition = ConditionDisposition(
            candidate=CANDIDATE, reviewer_module="materials",
            condition_id="fatigue-check", condition_text="validate interface fatigue",
            status=ConditionStatus.SATISFIED, rationale="Parent verified evidence",
            decided_by="parent_coordinator", decision_version=1,
            evidence=({"evidence_id": "ev-fatigue"},),
        )
        handler = create_cross_module_task_handler(
            registry=self.registry, module_bindings=self.bindings,
            adapters=self.adapters,
            disposition_provider=lambda candidate, reviews, context: (disposition,),
        )
        result = handler(self.task, self.context)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(
            self.context.checkpoint["task_state"]["assessment"]["decision"], "accepted"
        )


if __name__ == "__main__":
    unittest.main()
