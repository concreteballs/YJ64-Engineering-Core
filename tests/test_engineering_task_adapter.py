import json
import unittest

from yj64_engineering_core.automation.engineering_task_adapter import (
    EngineeringDispatcherTaskAdapter,
)
from yj64_engineering_core.automation.parent_tasks import ParentTaskState
from yj64_engineering_core.automation.worker import TaskExecutionResult
from yj64_engineering_core.contracts import EngineeringRequest, LoadCase
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher
from yj64_engineering_core.task_contracts import TaskRequest


class FakeContext:
    task_id = 42

    def __init__(self):
        self.checkpoints = []

    def load_latest_checkpoint(self):
        return self.checkpoints[-1] if self.checkpoints else None

    def save_checkpoint(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return True


class EngineeringTaskAdapterTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EngineeringDispatcher()
        self.dispatcher.register_physics_solver(AxialMemberSolver())
        self.adapter = EngineeringDispatcherTaskAdapter(self.dispatcher)
        self.context = FakeContext()
        self.state = ParentTaskState("new", {}, None, ())

    def task(self, operation="physics.axial_member", request_id="task-42"):
        engineering_request = EngineeringRequest(
            request_id=request_id,
            title="Axial bar screening",
            objective="Calculate preliminary axial stress and elongation",
            geometry={
                "geometry_type": "prismatic_member",
                "parameters": {"area_m2": 0.001, "length_m": 2.0},
            },
            material={
                "name": "Test steel",
                "youngs_modulus_pa": 200e9,
                "allowable_stress_pa": 150e6,
            },
            load_cases=(LoadCase(name="service", force_n=(0.0, 0.0, 1000.0)),),
        )
        return TaskRequest(
            task_id="task-42",
            task_type="engineering.analysis",
            title="Run axial analysis",
            objective="Run the explicitly requested engineering operation",
            input_data={
                "operation": operation,
                "engineering_request": json.loads(json.dumps(engineering_request.to_dict())),
            },
            requested_capabilities=("engineering.dispatch",),
        )

    def test_dispatches_to_existing_registered_solver_and_checkpoints_result(self):
        decision = self.adapter(self.task(), self.state, self.context)

        self.assertEqual(decision, TaskExecutionResult("completed"))
        checkpoint = self.context.checkpoints[0]
        self.assertEqual(checkpoint["state"], "completed")
        task_state = checkpoint["task_state"]
        self.assertEqual(task_state["operation"], "physics.axial_member")
        self.assertEqual(task_state["engineering_response"]["status"], "screening_only")
        self.assertEqual(task_state["engineering_response"]["values"]["stress_pa"], 1e6)

    def test_rejects_request_id_mismatch(self):
        decision = self.adapter(self.task(request_id="different-id"), self.state, self.context)
        self.assertEqual(decision, TaskExecutionResult("blocked", "engineering_request_id_mismatch"))
        self.assertEqual(self.context.checkpoints, [])

    def test_rejects_unregistered_solver_without_guessing(self):
        task = self.task(operation="physics.cfd")
        decision = self.adapter(task, self.state, self.context)
        self.assertEqual(decision, TaskExecutionResult("blocked", "engineering_backend_not_registered"))

    def test_refuses_to_discard_a_council_resume_event(self):
        resumed = ParentTaskState(
            "council_result_received",
            {},
            {"result_artifact_ref": "private://result"},
            ("private://result",),
        )
        decision = self.adapter(self.task(), resumed, self.context)
        self.assertEqual(
            decision,
            TaskExecutionResult("blocked", "engineering_adapter_cannot_consume_council_result"),
        )


if __name__ == "__main__":
    unittest.main()
