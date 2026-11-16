import math
import shutil
import tempfile
import unittest

from yj64_engineering_core.models import AnalysisResult
from yj64_engineering_core.physics.kernel import (
    AppliedLoad,
    BoundaryCondition,
    CoordinateFrame,
    CoordinateFrameRegistry,
    GeometryPoint,
    Quantity,
)
from yj64_engineering_core.physics.typed_calculix import TypedCalculiXAxialTrussSolver
from yj64_engineering_core.typed_solver import TypedSolverDispatcher, TypedSolverRequest


class FakeCalculiXSolver:
    def __init__(self):
        self.request = None

    def solve(self, request):
        self.request = request
        return AnalysisResult(
            analysis_type="axial_truss_fem",
            status="completed",
            values={"tip_displacement_z_m": 1e-5},
            units={"tip_displacement_z_m": "m"},
            method="fake CalculiX FEM",
            assumptions=["test assumption"],
            warnings=[],
            limitations=["test limitation"],
            solver_name="CalculiX test",
            solver_version="2.22-test",
        )


def make_request(force_unit="lbf", force_value=100.0, force_x=0.0):
    frames = CoordinateFrameRegistry()
    frames.add(CoordinateFrame("world"))
    load = AppliedLoad(
        load_id="load.tip",
        target_id="member:tip",
        kind="force",
        components=(
            Quantity(force_x, "N"),
            Quantity(0.0, "N"),
            Quantity(force_value, force_unit),
        ),
        frame_id="world",
        distribution="point",
        application_point=GeometryPoint(0.0, 0.0, 2.0, "world"),
    )
    fixed = BoundaryCondition(
        condition_id="bc.root",
        target_id="member:root",
        kind="fixed",
        frame_id="world",
    )
    return TypedSolverRequest(
        request_id="typed-ccx-001",
        operation="structural.axial_truss_fem",
        frame_registry=frames,
        loads=(load,),
        boundary_conditions=(fixed,),
        quantities={
            "member_length": Quantity(2000.0, "mm"),
            "cross_section_area": Quantity(1000.0, "mm2"),
            "youngs_modulus": Quantity(200000.0, "MPa"),
            "poisson_ratio": Quantity(0.3, "1"),
        },
    )


class TypedCalculiXAdapterTests(unittest.TestCase):
    def test_dispatches_typed_si_inputs_to_calculix_and_preserves_provenance(self):
        fake = FakeCalculiXSolver()
        with tempfile.TemporaryDirectory() as directory:
            adapter = TypedCalculiXAxialTrussSolver(directory, solver=fake)
            dispatcher = TypedSolverDispatcher()
            dispatcher.register(adapter)
            response = dispatcher.dispatch(make_request())

        self.assertEqual(response.status, "completed")
        self.assertEqual(response.solver_name, "CalculiX typed axial-truss FEM adapter")
        self.assertEqual(response.solver_version, "1.0.0")
        self.assertEqual(response.values["external_solver_version"], "2.22-test")
        self.assertAlmostEqual(
            fake.request.parameters["force_n"], 100.0 * 4.4482216152605
        )
        self.assertAlmostEqual(fake.request.parameters["length_m"], 2.0)
        self.assertAlmostEqual(fake.request.parameters["area_m2"], 0.001)
        self.assertEqual(len(response.input_digest_sha256), 64)

    def test_rejects_transverse_force_before_external_solver(self):
        fake = FakeCalculiXSolver()
        with tempfile.TemporaryDirectory() as directory:
            adapter = TypedCalculiXAxialTrussSolver(directory, solver=fake)
            with self.assertRaisesRegex(ValueError, "aligned"):
                adapter.solve(make_request(force_x=10.0))
        self.assertIsNone(fake.request)

    def test_rejects_wrong_tip_application_point(self):
        request = make_request()
        load = AppliedLoad(
            load_id="load.tip",
            target_id="member:tip",
            kind="force",
            components=(Quantity(0, "N"), Quantity(0, "N"), Quantity(100, "N")),
            frame_id="world",
            application_point=GeometryPoint(0, 0, 1.0, "world"),
        )
        request = TypedSolverRequest(
            request_id=request.request_id,
            operation=request.operation,
            frame_registry=request.frame_registry,
            loads=(load,),
            boundary_conditions=request.boundary_conditions,
            quantities=request.quantities,
        )
        fake = FakeCalculiXSolver()
        with tempfile.TemporaryDirectory() as directory:
            adapter = TypedCalculiXAxialTrussSolver(directory, solver=fake)
            with self.assertRaisesRegex(ValueError, "application point"):
                adapter.solve(request)
        self.assertIsNone(fake.request)


@unittest.skipUnless(shutil.which("ccx"), "CalculiX executable is not installed")
class TypedCalculiXRealIntegrationTests(unittest.TestCase):
    def test_typed_request_runs_real_calculix_and_matches_analytical_solution(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = TypedCalculiXAxialTrussSolver(directory, timeout_seconds=30)
            dispatcher = TypedSolverDispatcher()
            dispatcher.register(adapter)
            response = dispatcher.dispatch(make_request())

        force_n = 100.0 * 4.4482216152605
        expected_displacement_m = force_n * 2.0 / (0.001 * 200e9)
        self.assertEqual(response.status, "completed")
        self.assertTrue(response.values["external_solver_version"])
        self.assertAlmostEqual(
            response.values["tip_displacement_z_m"],
            expected_displacement_m,
            delta=expected_displacement_m * 1e-5,
        )
        self.assertEqual(response.units["tip_displacement_z_m"], "m")
        self.assertEqual(len(response.input_digest_sha256), 64)


if __name__ == "__main__":
    unittest.main()
