import math
import unittest

from yj64_engineering_core.models import AnalysisRequest
from yj64_engineering_core.physics.sail import SailAerodynamicsSolver, interpolate_sail_polar


POLAR = [
    {"alpha_deg": -10.0, "cl": -0.55, "cd": 0.08, "cm": 0.03},
    {"alpha_deg": 0.0, "cl": 0.0, "cd": 0.025, "cm": 0.0},
    {"alpha_deg": 10.0, "cl": 0.9, "cd": 0.06, "cm": -0.04},
    {"alpha_deg": 20.0, "cl": 1.1, "cd": 0.14, "cm": -0.08},
]


def make_request(**overrides):
    conditions = {
        "apparent_wind_speed_m_s": 10.0,
        "air_density_kg_m3": 1.225,
        "dynamic_viscosity_pa_s": 1.81e-5,
        "angle_of_attack_deg": 5.0,
        "apparent_wind_from_angle_deg": 45.0,
        "oswald_efficiency": 0.85,
    }
    conditions.update(overrides)
    return AnalysisRequest(
        analysis_type="aerodynamics.sail_polar",
        parameters={
            "geometry": {
                "sail_area_m2": 30.0,
                "span_m": 12.0,
                "mean_chord_m": 2.5,
                "polar_points": [dict(row) for row in POLAR],
                "polar_source": "unit-test polar",
            },
            "operating_conditions": conditions,
        },
    )


class SailPolarTests(unittest.TestCase):
    def test_linear_polar_interpolation(self):
        cl, cd, cm = interpolate_sail_polar(
            [(-10.0, -0.5, 0.1, 0.02), (10.0, 0.9, 0.05, -0.04)], 0.0
        )
        self.assertAlmostEqual(cl, 0.2)
        self.assertAlmostEqual(cd, 0.075)
        self.assertAlmostEqual(cm, -0.01)

    def test_sail_forces_and_induced_drag(self):
        result = SailAerodynamicsSolver().solve(make_request())
        self.assertEqual(result.status, "screening_only")
        self.assertAlmostEqual(result.values["dynamic_pressure_pa"], 61.25)
        self.assertAlmostEqual(result.values["lift_coefficient"], 0.45)
        self.assertAlmostEqual(result.values["profile_drag_coefficient"], 0.0425)
        expected_ar = 12.0**2 / 30.0
        expected_induced = 0.45**2 / (math.pi * 0.85 * expected_ar)
        self.assertAlmostEqual(result.values["aspect_ratio"], expected_ar)
        self.assertAlmostEqual(result.values["induced_drag_coefficient"], expected_induced)
        self.assertGreater(result.values["total_drag_force_n"], result.values["profile_drag_force_n"])
        self.assertEqual(result.units["aerodynamic_moment_nm"], "N*m")
        self.assertGreater(result.values["reynolds_number"], 0.0)

    def test_apparent_wind_direction_resolves_force_into_boat_axes(self):
        result = SailAerodynamicsSolver().solve(make_request(apparent_wind_from_angle_deg=0.0))
        self.assertLess(result.values["force_x_forward_n"], 0.0)
        self.assertLess(result.values["force_y_starboard_n"], 0.0)

    def test_zero_wind_produces_zero_loads(self):
        result = SailAerodynamicsSolver().solve(make_request(apparent_wind_speed_m_s=0.0))
        self.assertEqual(result.values["lift_force_n"], 0.0)
        self.assertEqual(result.values["total_drag_force_n"], 0.0)
        self.assertEqual(result.values["aerodynamic_moment_nm"], 0.0)

    def test_out_of_polar_range_is_rejected_without_extrapolation(self):
        with self.assertRaisesRegex(ValueError, "outside the supplied polar range"):
            SailAerodynamicsSolver().solve(make_request(angle_of_attack_deg=25.0))

    def test_polar_must_be_strictly_ordered(self):
        request = make_request()
        request.parameters["geometry"]["polar_points"] = [POLAR[0], POLAR[0]]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            SailAerodynamicsSolver().solve(request)

    def test_negative_profile_drag_is_rejected(self):
        request = make_request()
        request.parameters["geometry"]["polar_points"][1]["cd"] = -0.1
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            SailAerodynamicsSolver().solve(request)

    def test_invalid_oswald_efficiency_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            SailAerodynamicsSolver().solve(make_request(oswald_efficiency=1.2))


if __name__ == "__main__":
    unittest.main()
