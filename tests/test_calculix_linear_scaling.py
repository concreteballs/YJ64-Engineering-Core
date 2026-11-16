import shutil
import tempfile
import unittest

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


def axial_request(request_id: str, force_n: float) -> TypedSolverRequest:
    frames = CoordinateFrameRegistry()
    frames.add(CoordinateFrame("world"))
    load = AppliedLoad(
        load_id=f"{request_id}.load",
        target_id="member:tip",
        kind="force",
        components=(Quantity(0.0, "N"), Quantity(0.0, "N"), Quantity(force_n, "N")),
        frame_id="world",
        distribution="point",
        application_point=GeometryPoint(0.0, 0.0, 2.0, "world"),
    )
    root = BoundaryCondition(
        condition_id=f"{request_id}.root",
        target_id="member:root",
        kind="fixed",
        frame_id="world",
    )
    return TypedSolverRequest(
        request_id=request_id,
        operation="structural.axial_truss_fem",
        frame_registry=frames,
        loads=(load,),
        boundary_conditions=(root,),
        quantities={
            "member_length": Quantity(2.0, "m"),
            "cross_section_area": Quantity(0.001, "m2"),
            "youngs_modulus": Quantity(200.0, "GPa"),
            "poisson_ratio": Quantity(0.3, "1"),
        },
    )


@unittest.skipUnless(shutil.which("ccx"), "CalculiX executable is not installed")
class CalculiXLinearScalingTests(unittest.TestCase):
    def test_real_solver_obeys_linear_force_displacement_scaling_and_sign(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = TypedCalculiXAxialTrussSolver(directory, timeout_seconds=30)
            dispatcher = TypedSolverDispatcher()
            dispatcher.register(adapter)

            low = dispatcher.dispatch(axial_request("linear-low", 100.0))
            high = dispatcher.dispatch(axial_request("linear-high", 200.0))
            compression = dispatcher.dispatch(axial_request("linear-compression", -100.0))

        low_displacement = low.values["tip_displacement_z_m"]
        high_displacement = high.values["tip_displacement_z_m"]
        compression_displacement = compression.values["tip_displacement_z_m"]

        self.assertEqual(low.status, "completed")
        self.assertEqual(high.status, "completed")
        self.assertEqual(compression.status, "completed")
        self.assertAlmostEqual(high_displacement / low_displacement, 2.0, places=7)
        self.assertAlmostEqual(compression_displacement, -low_displacement, places=7)

        expected = 100.0 * 2.0 / (0.001 * 200e9)
        self.assertAlmostEqual(low_displacement, expected, delta=expected * 1e-5)


if __name__ == "__main__":
    unittest.main()
