import json
import unittest
from tempfile import TemporaryDirectory

from yj64_engineering_core.automation.engineering_runtime import (
    ENGINEERING_TASK_TYPE,
    create_engineering_task_registry,
    create_engineering_worker_runner,
    create_reference_engineering_dispatcher,
)
from yj64_engineering_core.automation.task_requests import PARENT_TASK_QUEUE_TYPE
from yj64_engineering_core.contracts import EngineeringRequest, LoadCase
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher
from yj64_engineering_core.task_contracts import TaskRequest


class FakeStore:
    def __init__(self, task):
        self.task = task
        self.checkpoint = None
        self.completed = []

    def run_recovery_maintenance(self, limit=100):
        return {"recovered": 0}

    def claim_next_task(self, worker_id, lease_seconds=300, task_types=None):
        if self.task is None:
            return None
        task, self.task = self.task, None
        if task_types is not None:
            assert task["task_type"] in task_types
        return task

    def load_latest_checkpoint(self, task_id):
        return self.checkpoint

    def save_checkpoint(self, task_id, worker_id, checkpoint, lease_seconds=300):
        self.checkpoint = checkpoint
        return True

    def complete_task(self, task_id, worker_id):
        self.completed.append(task_id)
        return True


def configured_dispatcher():
    dispatcher = EngineeringDispatcher()
    dispatcher.register_physics_solver(AxialMemberSolver())
    return dispatcher


def queued_engineering_task():
    engineering_request = EngineeringRequest(
        request_id="engineering-task-1",
        title="Axial member screening",
        objective="Calculate axial stress and elongation",
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
    request = TaskRequest(
        task_id="engineering-task-1",
        task_type=ENGINEERING_TASK_TYPE,
        title="Run axial analysis",
        objective="Execute the explicit physics operation",
        input_data={
            "operation": "physics.axial_member",
            "engineering_request": json.loads(json.dumps(engineering_request.to_dict())),
        },
        requested_capabilities=("engineering.dispatch",),
    )
    return {
        "task_id": 17,
        "task_type": PARENT_TASK_QUEUE_TYPE,
        "payload": {"task_request": request.to_dict()},
    }


class EngineeringRuntimeTests(unittest.TestCase):
    def test_reference_dispatcher_registers_real_axial_and_optional_cad_backends(self):
        with TemporaryDirectory() as workspace:
            dispatcher = create_reference_engineering_dispatcher(cad_workspace=workspace)
            request = EngineeringRequest(
                request_id="runtime-cad-1",
                title="Cylinder source",
                objective="Create editable CAD source",
                geometry={
                    "geometry_type": "cylinder",
                    "parameters": {"diameter_m": 0.1, "height_m": 0.2},
                },
                operating_conditions={"cad_backend": "openscad_source"},
            )
            result = dispatcher.dispatch(request, "cad.generate")
            self.assertEqual(result.response.status, "completed")
            self.assertEqual(result.response.artifacts[0].media_type, "application/x-openscad")

    def test_registry_contains_only_concrete_configured_engineering_adapter(self):
        registry = create_engineering_task_registry(configured_dispatcher())
        registration = registry.get(ENGINEERING_TASK_TYPE)
        self.assertIsNotNone(registration)
        self.assertEqual(registration.capabilities, frozenset({"engineering.dispatch"}))
        self.assertFalse(registration.council_enabled)

    def test_worker_runner_executes_universal_task_through_real_dispatcher(self):
        store = FakeStore(queued_engineering_task())
        runner = create_engineering_worker_runner(
            store,
            dispatcher=configured_dispatcher(),
            worker_id="engineering-worker",
        )

        result = runner.run_once()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(store.completed, [17])
        self.assertEqual(store.checkpoint["state"], "completed")
        response = store.checkpoint["task_state"]["engineering_response"]
        self.assertEqual(response["status"], "screening_only")
        self.assertEqual(response["values"]["stress_pa"], 1e6)

    def test_existing_handlers_are_preserved(self):
        extra = lambda task, context: None
        runner = create_engineering_worker_runner(
            FakeStore(None),
            dispatcher=configured_dispatcher(),
            worker_id="engineering-worker",
            additional_handlers={"process_ci_event": extra},
        )
        self.assertIn("process_ci_event", runner.handlers)
        self.assertIn(PARENT_TASK_QUEUE_TYPE, runner.handlers)
        self.assertIn("process_ci_event", runner.allowed_task_types)

    def test_reserved_parent_handler_cannot_be_overridden(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            create_engineering_worker_runner(
                FakeStore(None),
                dispatcher=configured_dispatcher(),
                worker_id="engineering-worker",
                additional_handlers={PARENT_TASK_QUEUE_TYPE: lambda *_: None},
            )


if __name__ == "__main__":
    unittest.main()
