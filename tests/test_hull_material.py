import unittest

from yj64_engineering_core import EngineeringDispatcher, EngineeringRequest, HullMaterialScreeningSolver
from yj64_engineering_core.models import AnalysisRequest


class HullMaterialScreeningTests(unittest.TestCase):
    def test_compares_aluminium_composite_and_concrete_build_ups(self):
        request = AnalysisRequest("hull.material_screen", {"operating_conditions": {"alternatives": [
            {
                "name": "marine aluminium plate",
                "material_family": "aluminium",
                "construction_type": "monolithic",
                "structural_area_m2": 100.0,
                "layers": [{"name": "5083 plate", "thickness_m": 0.004, "density_kg_m3": 2660}],
                "material_cost_eur_m2": 85.0,
                "manufacturing_cost_eur_m2": 45.0,
                "annual_maintenance_cost_eur": 1200.0,
            },
            {
                "name": "carbon sandwich",
                "material_family": "carbon_fiber_composite",
                "construction_type": "sandwich",
                "structural_area_m2": 100.0,
                "layers": [
                    {"name": "outer cured carbon laminate", "areal_mass_kg_m2": 1.8},
                    {"name": "honeycomb core", "thickness_m": 0.02, "density_kg_m3": 80},
                    {"name": "inner cured carbon laminate", "areal_mass_kg_m2": 1.8},
                ],
                "secondary_mass_kg": 80.0,
                "material_cost_eur_m2": 210.0,
                "manufacturing_cost_eur_m2": 180.0,
                "annual_maintenance_cost_eur": 500.0,
            },
            {
                "name": "reinforced concrete",
                "material_family": "reinforced_concrete",
                "construction_type": "monolithic",
                "structural_area_m2": 100.0,
                "layers": [{"name": "reinforced concrete", "thickness_m": 0.06, "density_kg_m3": 2500}],
                "material_cost_eur_m2": 55.0,
                "annual_maintenance_cost_eur": 900.0,
            },
        ]}})
        result = HullMaterialScreeningSolver().solve(request)
        alternatives = result.values["alternatives"]
        self.assertEqual(len(alternatives), 3)
        self.assertAlmostEqual(alternatives[0]["installed_hull_build_up_mass_kg"], 1064.0)
        self.assertAlmostEqual(alternatives[1]["installed_hull_build_up_mass_kg"], 600.0)
        self.assertAlmostEqual(alternatives[2]["installed_hull_build_up_mass_kg"], 15000.0)
        self.assertAlmostEqual(alternatives[0]["known_build_cost_eur"], 13000.0)
        self.assertEqual(alternatives[1]["annual_maintenance_cost_eur"], 500.0)

    def test_rejects_wood_and_unlisted_materials(self):
        request = AnalysisRequest("hull.material_screen", {"operating_conditions": {"alternatives": [{
            "name": "wood", "material_family": "wood", "structural_area_m2": 10,
            "layers": [{"areal_mass_kg_m2": 5}],
        }]}})
        with self.assertRaisesRegex(ValueError, "unsupported material_family"):
            HullMaterialScreeningSolver().solve(request)

    def test_rejects_missing_layer_density_or_areal_mass(self):
        request = AnalysisRequest("hull.material_screen", {"operating_conditions": {"alternatives": [{
            "name": "bad layer", "material_family": "glass_fiber_composite",
            "structural_area_m2": 10, "layers": [{"thickness_m": 0.01}],
        }]}})
        with self.assertRaisesRegex(ValueError, "requires areal_mass"):
            HullMaterialScreeningSolver().solve(request)

    def test_dispatcher_route(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(HullMaterialScreeningSolver())
        request = EngineeringRequest(
            request_id="hull-material-001",
            title="Hull material comparison",
            objective="Compare mass and lifecycle cost inputs",
            operating_conditions={"alternatives": [{
                "name": "glass sandwich",
                "material_family": "glass_fiber_composite",
                "construction_type": "sandwich",
                "structural_area_m2": 20,
                "layers": [{"areal_mass_kg_m2": 3.0}],
            }]},
        )
        result = dispatcher.dispatch(request, "physics.hull.material_screen")
        self.assertEqual(result.response.status, "screening_only")
        self.assertAlmostEqual(
            result.response.values["alternatives"][0]["installed_hull_build_up_mass_kg"],
            60.0,
        )


if __name__ == "__main__":
    unittest.main()
