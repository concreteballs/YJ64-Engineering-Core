import tempfile
import unittest
from pathlib import Path

from yj64_engineering_core.persistence import ProjectStore
from yj64_engineering_core.physics.kernel import (
    AppliedLoad, BoundaryCondition, CoordinateFrame, CoordinateFrameRegistry,
    GeometryPoint, Quantity,
)
from yj64_engineering_core.typed_solver import (
    TypedSolverDispatcher, TypedSolverRequest, TypedSolverResult,
)


class ReferenceTypedSolver:
    name = "YJ64 typed integration reference"
    version = "1.0.0"

    def supports(self, operation):
        return operation == "structural.integration_probe"

    def solve(self, request):
        force_loads = [load for load in request.loads if load.kind == "force"]
        force = sum(
            component.si_value
            for load in force_loads
            for component in load.components
        )
        return TypedSolverResult(
            status="screening_only",
            method="deterministic typed-input integration probe",
            values={
                "force_component_sum_n": force,
                "load_count": len(request.loads),
                "boundary_condition_count": len(request.boundary_conditions),
                "temperature_k": request.quantities["ambient_temperature"].si_value,
            },
            units={
                "force_component_sum_n": "N",
                "load_count": "count",
                "boundary_condition_count": "count",
                "temperature_k": "K",
            },
            assumptions=("Integration test only; no physical model is solved.",),
        )


def make_request(component_revision=1):
    frames = CoordinateFrameRegistry()
    frames.add(CoordinateFrame("world"))
    frames.add(CoordinateFrame(
        "actuator_local", parent_id="world",
        translation_to_parent_m=(0.0, 0.0, 0.25),
    ))
    load = AppliedLoad(
        load_id="load.axial",
        target_id="actuator",
        kind="force",
        components=(Quantity(10, "N"), Quantity(0, "N"), Quantity(2, "lbf")),
        frame_id="actuator_local",
        application_point=GeometryPoint(0.0, 0.0, 0.1, "actuator_local"),
    )
    fixed = BoundaryCondition(
        condition_id="bc.mount",
        target_id="mount",
        kind="fixed",
        frame_id="world",
    )
    displacement = BoundaryCondition(
        condition_id="bc.travel",
        target_id="slider",
        kind="displacement",
        components=(Quantity(0, "mm"), Quantity(0, "mm"), Quantity(5, "mm")),
        frame_id="actuator_local",
    )
    return TypedSolverRequest(
        request_id="integration.typed.001",
        operation="structural.integration_probe",
        frame_registry=frames,
        loads=(load,),
        boundary_conditions=(fixed, displacement),
        quantities={"ambient_temperature": Quantity(20, "degC")},
        component_dependencies=({"component_id": "actuator", "revision": component_revision},),
    )


class TypedSolverIntegrationTests(unittest.TestCase):
    def test_typed_inputs_dispatch_persist_and_become_stale(self):
        dispatcher = TypedSolverDispatcher()
        dispatcher.register(ReferenceTypedSolver())
        request = make_request()
        response = dispatcher.dispatch(request)

        self.assertEqual(response.status, "screening_only")
        self.assertEqual(response.solver_name, "YJ64 typed integration reference")
        self.assertEqual(response.units["force_component_sum_n"], "N")
        self.assertAlmostEqual(response.values["temperature_k"], 293.15)
        self.assertEqual(len(response.input_digest_sha256), 64)

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "typed-integration.sqlite"
            with ProjectStore(database) as store:
                store.create_project("robot.demo", "Typed solver integration demo")
                store.save_snapshot(
                    "robot.demo",
                    {"components": [{"component_id": "actuator", "revision": 1}]},
                    expected_revision=0,
                )
                calculation = store.record_calculation(
                    calculation_id="calc.typed.001",
                    project_id="robot.demo",
                    operation=response.operation,
                    input_digest_sha256=response.input_digest_sha256,
                    result=response.to_dict(),
                    solver_name=response.solver_name,
                    solver_version=response.solver_version,
                    dependencies=request.component_dependencies,
                )
                self.assertEqual(calculation.status, "current")
                artifact = store.record_artifact(
                    artifact_id="artifact.typed.001",
                    project_id="robot.demo",
                    media_type="application/json",
                    uri="artifact://typed-integration/result.json",
                    calculation_id=calculation.calculation_id,
                    metadata={"evidence_level": "software_integration_test"},
                )
                self.assertEqual(artifact.status, "current")

                store.save_snapshot(
                    "robot.demo",
                    {"components": [{"component_id": "actuator", "revision": 2}]},
                    expected_revision=1,
                )
                self.assertEqual(store.list_calculations("robot.demo")[0].status, "stale")
                self.assertEqual(store.list_artifacts("robot.demo")[0].status, "stale")

    def test_unknown_load_frame_is_rejected_before_solver_execution(self):
        frames = CoordinateFrameRegistry()
        frames.add(CoordinateFrame("world"))
        load = AppliedLoad(
            load_id="load.bad",
            target_id="part",
            kind="force",
            components=(Quantity(1, "N"), Quantity(0, "N"), Quantity(0, "N")),
            frame_id="missing_frame",
        )
        with self.assertRaisesRegex(ValueError, "unknown frame"):
            TypedSolverRequest(
                request_id="bad.frame",
                operation="structural.integration_probe",
                frame_registry=frames,
                loads=(load,),
            )

    def test_solver_registration_rejects_duplicate_identity(self):
        dispatcher = TypedSolverDispatcher()
        dispatcher.register(ReferenceTypedSolver())
        with self.assertRaisesRegex(ValueError, "already registered"):
            dispatcher.register(ReferenceTypedSolver())


if __name__ == "__main__":
    unittest.main()
