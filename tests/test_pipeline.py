import json
import tempfile
import unittest
from pathlib import Path

from yj64_engineering_core.cad.adapters import OpenSCADSourceBackend
from yj64_engineering_core.contracts import EngineeringRequest, GeometrySpec, LoadCase
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher
from yj64_engineering_core.pipeline import EngineeringPipeline


class EngineeringPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.dispatcher = EngineeringDispatcher()
        self.dispatcher.register_physics_solver(AxialMemberSolver())
        self.dispatcher.register_cad_backend(
            "openscad", OpenSCADSourceBackend(self.workspace)
        )
        self.pipeline = EngineeringPipeline(self.dispatcher)

    def tearDown(self):
        self.tempdir.cleanup()

    def make_request(self, geometry_type="cylinder", force=(0.0, 0.0, 1000.0)):
        return EngineeringRequest(
            request_id="pipeline-test-001",
            title="Pipeline test member",
            objective="Run independent CAD generation and axial screening",
            geometry=GeometrySpec(
                geometry_type,
                {
                    "diameter_m": 0.05,
                    "height_m": 0.12,
                    "area_m2": 0.001,
                    "length_m": 2.0,
                },
            ),
            material={
                "name": "Test steel",
                "youngs_modulus_pa": 200e9,
                "allowable_stress_pa": 150e6,
            },
            load_cases=(LoadCase(name="service", force_n=force),),
            operating_conditions={"cad_backend": "openscad"},
            assumptions=("Test input only; not a certified design.",),
        )

    def test_runs_both_branches_and_returns_combined_result(self):
        result = self.pipeline.run(
            self.make_request(), physics_operation="physics.axial_member"
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.branches["physics"].execution_status, "completed")
        self.assertEqual(result.branches["cad"].execution_status, "completed")
        self.assertEqual(
            result.branches["physics"].result.response.values["stress_pa"], 1e6
        )
        self.assertTrue((self.workspace / "pipeline-test-001.scad").is_file())
        self.assertEqual(result.to_dict()["request_id"], "pipeline-test-001")
        self.assertEqual(json.loads(result.to_json())["status"], "completed")

    def test_physics_failure_does_not_suppress_cad(self):
        result = self.pipeline.run(
            self.make_request(force=(100.0, 0.0, 1000.0)),
            physics_operation="physics.axial_member",
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.branches["physics"].execution_status, "error")
        self.assertIn(
            "Z-axis axial force",
            result.branches["physics"].error_message,
        )
        self.assertEqual(result.branches["cad"].execution_status, "completed")
        self.assertTrue((self.workspace / "pipeline-test-001.scad").is_file())

    def test_cad_failure_does_not_suppress_physics(self):
        result = self.pipeline.run(
            self.make_request(geometry_type="gear"),
            physics_operation="physics.axial_member",
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.branches["cad"].execution_status, "error")
        self.assertIn("cylinder geometry only", result.branches["cad"].error_message)
        self.assertEqual(result.branches["physics"].execution_status, "completed")

    def test_both_branch_failures_are_reported(self):
        request = self.make_request(geometry_type="gear", force=(100.0, 0.0, 1000.0))
        result = self.pipeline.run(request, physics_operation="physics.axial_member")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.branches["physics"].execution_status, "error")
        self.assertEqual(result.branches["cad"].execution_status, "error")

    def test_rejects_non_physics_operation(self):
        with self.assertRaisesRegex(ValueError, "physics_operation"):
            self.pipeline.run(self.make_request(), physics_operation="cad.generate")

    def test_rejects_unknown_cad_operation(self):
        with self.assertRaisesRegex(ValueError, "cad_operation"):
            self.pipeline.run(
                self.make_request(),
                physics_operation="physics.axial_member",
                cad_operation="cad.auto",
            )


if __name__ == "__main__":
    unittest.main()
