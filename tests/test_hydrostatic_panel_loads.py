import math
import unittest

from yj64_engineering_core import (
    EngineeringDispatcher,
    EngineeringRequest,
    GeometrySpec,
    HydrostaticPanelLoadSolver,
)
from yj64_engineering_core.models import AnalysisRequest


def make_request(panels=None, conditions=None):
    return AnalysisRequest(
        "hydrostatics.panel_pressure_loads",
        {
            "geometry": {
                "panels": panels if panels is not None else [
                    {
                        "panel_id": "bottom",
                        "area_m2": 2.0,
                        "centroid_m": [0.0, 0.0, -2.0],
                        "outward_normal": [0.0, 0.0, -1.0],
                    }
                ]
            },
            "operating_conditions": {
                "waterline_z_m": 0.0,
                "water_density_kg_m3": 1025.0,
                "gravity_m_s2": 9.80665,
                "internal_gauge_pressure_pa": 0.0,
                **(conditions or {}),
            },
        },
    )


class HydrostaticPanelLoadTests(unittest.TestCase):
    def setUp(self):
        self.solver = HydrostaticPanelLoadSolver()

    def test_pressure_and_force_on_submerged_bottom_panel(self):
        result = self.solver.solve(make_request())
        pressure = 1025.0 * 9.80665 * 2.0
        self.assertAlmostEqual(
            result.values["panels"][0]["external_hydrostatic_pressure_pa"],
            pressure,
        )
        self.assertAlmostEqual(result.values["total_force_xyz_n"][2], 2.0 * pressure)
        self.assertEqual(result.values["panels"][0]["loading_direction"], "inward")
        self.assertEqual(result.status, "screening_only")

    def test_panel_above_waterline_has_zero_external_pressure(self):
        panels = [{
            "panel_id": "deck",
            "area_m2": 1.0,
            "centroid_m": [0.0, 0.0, 1.0],
            "outward_normal": [0.0, 0.0, 1.0],
        }]
        result = self.solver.solve(make_request(panels))
        self.assertEqual(
            result.values["panels"][0]["external_hydrostatic_pressure_pa"], 0.0
        )
        self.assertEqual(result.values["total_force_xyz_n"], [0.0, 0.0, 0.0])

    def test_force_scales_with_panel_area_and_normal_direction(self):
        panels = [
            {
                "panel_id": "side",
                "area_m2": 1.0,
                "centroid_m": [1.0, 0.0, -1.0],
                "outward_normal": [1.0, 0.0, 0.0],
            },
            {
                "panel_id": "side_double",
                "area_m2": 2.0,
                "centroid_m": [2.0, 0.0, -1.0],
                "outward_normal": [1.0, 0.0, 0.0],
            },
        ]
        result = self.solver.solve(make_request(panels))
        pressure = 1025.0 * 9.80665
        self.assertAlmostEqual(result.values["total_force_xyz_n"][0], -3.0 * pressure)

    def test_internal_pressure_cancels_external_and_reverses_above_water(self):
        pressure_at_two_metres = 1025.0 * 9.80665 * 2.0
        panels = [
            {
                "panel_id": "submerged",
                "area_m2": 1.0,
                "centroid_m": [0.0, 0.0, -2.0],
                "outward_normal": [0.0, 0.0, -1.0],
            },
            {
                "panel_id": "dry",
                "area_m2": 1.0,
                "centroid_m": [0.0, 0.0, 1.0],
                "outward_normal": [0.0, 0.0, 1.0],
            },
        ]
        result = self.solver.solve(make_request(
            panels, {"internal_gauge_pressure_pa": pressure_at_two_metres}
        ))
        self.assertAlmostEqual(
            result.values["panels"][0]["differential_pressure_pa"], 0.0
        )
        self.assertEqual(result.values["panels"][1]["loading_direction"], "outward")
        self.assertAlmostEqual(
            result.values["panels"][1]["force_xyz_n"][2], pressure_at_two_metres
        )

    def test_moment_about_global_origin(self):
        panel = [{
            "panel_id": "offset",
            "area_m2": 1.0,
            "centroid_m": [1.0, 0.0, -1.0],
            "outward_normal": [1.0, 0.0, 0.0],
        }]
        result = self.solver.solve(make_request(panel))
        pressure = 1025.0 * 9.80665
        self.assertAlmostEqual(
            result.values["total_moment_about_origin_xyz_nm"][1], pressure
        )

    def test_invalid_area_normal_and_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            self.solver.solve(make_request([{
                "panel_id": "bad", "area_m2": 0.0,
                "centroid_m": [0, 0, 0], "outward_normal": [0, 0, 1],
            }]))
        with self.assertRaisesRegex(ValueError, "unit vector"):
            self.solver.solve(make_request([{
                "panel_id": "bad", "area_m2": 1.0,
                "centroid_m": [0, 0, 0], "outward_normal": [0, 0, 2],
            }]))
        duplicate = [
            {"panel_id": "same", "area_m2": 1, "centroid_m": [0,0,-1], "outward_normal": [0,0,-1]},
            {"panel_id": "same", "area_m2": 1, "centroid_m": [0,0,-2], "outward_normal": [0,0,-1]},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate panel_id"):
            self.solver.solve(make_request(duplicate))

    def test_dispatcher_integration(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(self.solver)
        request = EngineeringRequest(
            request_id="hull-pressure-001",
            title="Hull hydrostatic panel loads",
            objective="Generate hydrostatic pressure loads for wetted hull panels",
            geometry=GeometrySpec("panel_mesh", {
                "panels": [{
                    "panel_id": "bottom",
                    "area_m2": 2.0,
                    "centroid_m": [0.0, 0.0, -2.0],
                    "outward_normal": [0.0, 0.0, -1.0],
                }]
            }),
            operating_conditions={"waterline_z_m": 0.0},
        )
        response = dispatcher.dispatch(
            request, "physics.hydrostatics.panel_pressure_loads"
        ).response
        self.assertEqual(response.status, "screening_only")
        self.assertEqual(response.request_id, "hull-pressure-001")
        self.assertEqual(len(response.provenance.input_digest_sha256), 64)


    def test_polygon_integration_captures_pressure_gradient_and_resultant_centroid(self):
        panel = [{
            "panel_id": "vertical-side",
            "area_m2": 4.0,
            "centroid_m": [0.0, 1.0, -2.0],
            "outward_normal": [1.0, 0.0, 0.0],
            "vertices_m": [
                [0.0, 0.0, -1.0], [0.0, 2.0, -1.0],
                [0.0, 2.0, -3.0], [0.0, 0.0, -3.0],
            ],
        }]
        result = self.solver.solve(make_request(panel))
        rho_g = 1025.0 * 9.80665
        item = result.values["panels"][0]
        self.assertAlmostEqual(item["differential_pressure_pa"], 2.0 * rho_g)
        self.assertAlmostEqual(item["force_xyz_n"][0], -8.0 * rho_g)
        self.assertAlmostEqual(item["pressure_resultant_centroid_m"][2], -13.0 / 6.0)
        self.assertAlmostEqual(
            item["moment_about_origin_xyz_nm"][1], (13.0 / 6.0) * 8.0 * rho_g
        )
        self.assertEqual(item["integration_method"], "polygon_integrated_linear_pressure")

    def test_polygon_rejects_waterline_crossing_and_area_mismatch(self):
        crossing = [{
            "panel_id": "crossing", "area_m2": 2.0,
            "centroid_m": [0.0, 0.0, 0.0], "outward_normal": [1.0, 0.0, 0.0],
            "vertices_m": [[0, 0, -1], [0, 1, -1], [0, 1, 1], [0, 0, 1]],
        }]
        with self.assertRaisesRegex(ValueError, "crosses the waterline"):
            self.solver.solve(make_request(crossing))
        mismatch = [{
            "panel_id": "mismatch", "area_m2": 3.0,
            "centroid_m": [0.0, 0.5, -1.0], "outward_normal": [1.0, 0.0, 0.0],
            "vertices_m": [[0, 0, -1], [0, 1, -1], [0, 1, -2], [0, 0, -2]],
        }]
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.solver.solve(make_request(mismatch))

    def test_polygon_rejects_non_planar_geometry(self):
        panel = [{
            "panel_id": "nonplanar", "area_m2": 1.0,
            "centroid_m": [0.0, 0.5, -1.0], "outward_normal": [1.0, 0.0, 0.0],
            "vertices_m": [[0, 0, -1], [0, 1, -1], [0.1, 1, -2], [0, 0, -2]],
        }]
        with self.assertRaisesRegex(ValueError, "must be planar"):
            self.solver.solve(make_request(panel))


if __name__ == "__main__":
    unittest.main()
