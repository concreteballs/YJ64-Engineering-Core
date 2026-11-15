import unittest

from yj64_engineering_core.models import AnalysisRequest
from yj64_engineering_core import EngineeringDispatcher, EngineeringRequest, GeometrySpec
from yj64_engineering_core.physics.sail_material import SailMaterialSolver
from yj64_engineering_core.physics.apparent_wind import ApparentWindSolver


class SailMaterialTests(unittest.TestCase):
    def request(self, material):
        return AnalysisRequest(analysis_type="sail.material_screen", parameters={
            "geometry": {"sail_area_m2": 120.0}, "material": material,
        })

    def test_areal_density_and_construction_mass(self):
        result = SailMaterialSolver().solve(self.request({
            "areal_density_kg_m2": 0.25,
            "seam_and_overlap_fraction": 0.08,
            "reinforcement_mass_kg": 6.0,
            "hardware_mass_kg": 4.0,
            "warp_tensile_stiffness_n_m": 80000.0,
            "weft_tensile_stiffness_n_m": 55000.0,
            "in_plane_shear_stiffness_n_m": 12000.0,
        }))
        self.assertAlmostEqual(result.values["estimated_fabric_area_m2"], 129.6)
        self.assertAlmostEqual(result.values["fabric_mass_kg"], 32.4)
        self.assertAlmostEqual(result.values["estimated_total_sail_mass_kg"], 42.4)
        self.assertEqual(result.values["warp_tensile_stiffness_n_m"], 80000.0)
        self.assertEqual(result.values["weft_tensile_stiffness_n_m"], 55000.0)

    def test_bulk_density_times_thickness_fallback(self):
        result = SailMaterialSolver().solve(self.request({
            "bulk_density_kg_m3": 1400.0, "thickness_m": 0.0002,
        }))
        self.assertAlmostEqual(result.values["material_areal_density_kg_m2"], 0.28)
        self.assertAlmostEqual(result.values["fabric_mass_kg"], 33.6)

    def test_requires_mass_basis(self):
        with self.assertRaisesRegex(ValueError, "provide areal_density"):
            SailMaterialSolver().solve(self.request({}))

    def test_negative_construction_allowance_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            SailMaterialSolver().solve(self.request({
                "areal_density_kg_m2": 0.2, "reinforcement_mass_kg": -1,
            }))


class ApparentWindTests(unittest.TestCase):
    def solve(self, **conditions):
        return ApparentWindSolver().solve(AnalysisRequest(
            analysis_type="aerodynamics.apparent_wind",
            parameters={"operating_conditions": conditions},
        ))

    def test_headwind_and_forward_speed_add(self):
        result = self.solve(
            true_wind_speed_m_s=10.0, true_wind_from_angle_deg=0.0,
            vessel_velocity_x_forward_m_s=5.0, vessel_velocity_y_starboard_m_s=0.0,
        )
        self.assertAlmostEqual(result.values["apparent_wind_speed_m_s"], 15.0)
        self.assertAlmostEqual(result.values["apparent_wind_from_angle_deg"], 0.0)

    def test_tailwind_and_forward_speed_subtract(self):
        result = self.solve(
            true_wind_speed_m_s=10.0, true_wind_from_angle_deg=180.0,
            vessel_velocity_x_forward_m_s=5.0, vessel_velocity_y_starboard_m_s=0.0,
        )
        self.assertAlmostEqual(result.values["apparent_wind_speed_m_s"], 5.0)
        self.assertAlmostEqual(abs(result.values["apparent_wind_from_angle_deg"]), 180.0)

    def test_zero_true_wind_with_boat_motion(self):
        result = self.solve(
            true_wind_speed_m_s=0.0, true_wind_from_angle_deg=0.0,
            vessel_velocity_x_forward_m_s=6.0, vessel_velocity_y_starboard_m_s=0.0,
        )
        self.assertAlmostEqual(result.values["apparent_wind_speed_m_s"], 6.0)
        self.assertAlmostEqual(result.values["apparent_wind_from_angle_deg"], 0.0)

    def test_negative_wind_speed_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            self.solve(
                true_wind_speed_m_s=-1.0, true_wind_from_angle_deg=0.0,
                vessel_velocity_x_forward_m_s=0.0, vessel_velocity_y_starboard_m_s=0.0,
            )


class DispatcherIntegrationTests(unittest.TestCase):
    def test_material_solver_dispatch(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(SailMaterialSolver())
        request = EngineeringRequest(
            request_id="sail-material-dispatch",
            title="Sail material",
            objective="Estimate sail fabric mass",
            geometry=GeometrySpec("sail", {"sail_area_m2": 100.0}),
            material={"areal_density_kg_m2": 0.3},
        )
        result = dispatcher.dispatch(request, "physics.sail.material_screen")
        self.assertAlmostEqual(result.response.values["fabric_mass_kg"], 30.0)

    def test_apparent_wind_solver_dispatch(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(ApparentWindSolver())
        request = EngineeringRequest(
            request_id="apparent-wind-dispatch",
            title="Apparent wind",
            objective="Calculate apparent wind",
            operating_conditions={
                "true_wind_speed_m_s": 8.0,
                "true_wind_from_angle_deg": 0.0,
                "vessel_velocity_x_forward_m_s": 2.0,
                "vessel_velocity_y_starboard_m_s": 0.0,
            },
        )
        result = dispatcher.dispatch(request, "physics.aerodynamics.apparent_wind")
        self.assertAlmostEqual(result.response.values["apparent_wind_speed_m_s"], 10.0)


if __name__ == "__main__":
    unittest.main()
