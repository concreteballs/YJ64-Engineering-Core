import unittest

from yj64_engineering_core.models import AnalysisRequest
from yj64_engineering_core.physics.aerodynamics import AerodynamicsSolver
from yj64_engineering_core.physics.hydrodynamics import HydrodynamicsSolver


def make_request(analysis_type, speed=10.0):
    return AnalysisRequest(
        analysis_type=analysis_type,
        parameters={
            "geometry": {
                "reference_area_m2": 20.0,
                "characteristic_length_m": 5.0,
            },
            "operating_conditions": {
                "flow_speed_m_s": speed,
                "fluid_density_kg_m3": 1.225 if analysis_type.startswith("aero") else 1025.0,
                "dynamic_viscosity_pa_s": 1.81e-5 if analysis_type.startswith("aero") else 1.05e-3,
                "lift_coefficient": 1.0,
                "drag_coefficient": 0.1,
                "side_force_coefficient": 0.2,
            },
        },
    )


class FlowModelTests(unittest.TestCase):
    def test_aerodynamics_dynamic_pressure_and_forces(self):
        result = AerodynamicsSolver().solve(
            make_request("aerodynamics.coefficient_forces")
        )
        self.assertEqual(result.status, "screening_only")
        self.assertAlmostEqual(result.values["dynamic_pressure_pa"], 61.25)
        self.assertAlmostEqual(result.values["lift_force_n"], 1225.0)
        self.assertAlmostEqual(result.values["drag_force_n"], 122.5)
        self.assertGreater(result.values["reynolds_number"], 0)
        self.assertTrue(any("not a CFD" in warning for warning in result.warnings))

    def test_hydrodynamics_uses_water_density(self):
        result = HydrodynamicsSolver().solve(
            make_request("hydrodynamics.coefficient_forces", speed=2.0)
        )
        self.assertAlmostEqual(result.values["dynamic_pressure_pa"], 2050.0)
        self.assertAlmostEqual(result.values["lift_force_n"], 41000.0)
        self.assertEqual(result.units["lift_force_n"], "N")

    def test_negative_speed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            AerodynamicsSolver().solve(
                make_request("aerodynamics.coefficient_forces", speed=-1.0)
            )

    def test_negative_drag_coefficient_is_rejected(self):
        request = make_request("hydrodynamics.coefficient_forces")
        request.parameters["operating_conditions"]["drag_coefficient"] = -0.1
        with self.assertRaisesRegex(ValueError, "drag_coefficient"):
            HydrodynamicsSolver().solve(request)

    def test_zero_speed_returns_zero_forces_with_warning(self):
        result = HydrodynamicsSolver().solve(
            make_request("hydrodynamics.coefficient_forces", speed=0.0)
        )
        self.assertEqual(result.values["lift_force_n"], 0.0)
        self.assertTrue(any("Zero flow speed" in warning for warning in result.warnings))

    def test_solver_rejects_wrong_analysis_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported analysis type"):
            AerodynamicsSolver().solve(make_request("hydrodynamics.coefficient_forces"))


if __name__ == "__main__":
    unittest.main()
