import unittest

from yj64_engineering_core import (
    CatamaranHydrostaticsSolver,
    EngineeringDispatcher,
    EngineeringRequest,
    GeometrySpec,
    VesselMassBudgetSolver,
)
from yj64_engineering_core.models import AnalysisRequest


def hull():
    # Rectangular-prismatic section envelope used only as a deterministic test shape.
    return {"chine_fraction": 0.72, "stations": [
        {"x_m": 0.0, "half_beam_m": 1.0, "keel_z_m": 0.0, "chine_z_m": 1.0, "deck_z_m": 2.0},
        {"x_m": 5.0, "half_beam_m": 1.0, "keel_z_m": 0.0, "chine_z_m": 1.0, "deck_z_m": 2.0},
        {"x_m": 10.0, "half_beam_m": 1.0, "keel_z_m": 0.0, "chine_z_m": 1.0, "deck_z_m": 2.0},
    ]}


class CatamaranHydrostaticsTests(unittest.TestCase):
    def test_twin_hull_displacement_and_reserve(self):
        request = AnalysisRequest("hydrostatics.catamaran_displacement", {
            "geometry": {"hulls": [hull(), hull()]},
            "operating_conditions": {
                "design_waterline_z_m": 1.0,
                "maximum_waterline_z_m": 1.5,
                "water_density_kg_m3": 1000.0,
            },
        })
        result = CatamaranHydrostaticsSolver().solve(request)
        self.assertAlmostEqual(result.values["design_displacement_volume_m3"], 14.4)
        self.assertAlmostEqual(result.values["design_displacement_mass_kg"], 14400.0)
        self.assertGreater(result.values["maximum_displacement_mass_kg"], 20000.0)
        self.assertGreater(result.values["reserve_buoyancy_fraction_of_max"], 0.0)

    def test_requires_exactly_two_hulls(self):
        request = AnalysisRequest("hydrostatics.catamaran_displacement", {
            "geometry": {"hulls": [hull()]},
            "operating_conditions": {"design_waterline_z_m": 1.0, "maximum_waterline_z_m": 1.5},
        })
        with self.assertRaisesRegex(ValueError, "exactly two"):
            CatamaranHydrostaticsSolver().solve(request)


class VesselMassBudgetTests(unittest.TestCase):
    def test_items_tanks_and_centre_of_gravity(self):
        request = AnalysisRequest("vessel.mass_budget", {"operating_conditions": {
            "items": [
                {"name": "hull structure", "category": "structure", "mass_kg": 1000, "x_m": 5, "y_m": 0, "z_m": 1},
                {"name": "battery", "category": "propulsion", "mass_kg": 500, "x_m": 6, "y_m": 1, "z_m": 0.5},
            ],
            "tanks": [{
                "name": "fresh water", "capacity_m3": 2.0, "fill_fraction": 1.0,
                "fluid_density_kg_m3": 1000.0, "tank_and_fittings_mass_kg": 100,
                "category": "systems", "x_m": 4, "y_m": -1, "z_m": 0.4,
            }],
            "design_displacement_limit_kg": 3000.0,
        }})
        result = VesselMassBudgetSolver().solve(request)
        self.assertAlmostEqual(result.values["total_mass_kg"], 3600.0)
        self.assertAlmostEqual(result.values["tank_loaded_mass_kg"], 2100.0)
        self.assertEqual(result.values["payload_status"], "over_mass_limit")
        self.assertAlmostEqual(result.values["mass_margin_to_design_displacement_kg"], -600.0)
        self.assertAlmostEqual(result.values["longitudinal_cg_x_m"], (1000*5 + 500*6 + 2100*4)/3600)

    def test_invalid_tank_fill_rejected(self):
        request = AnalysisRequest("vessel.mass_budget", {"operating_conditions": {
            "items": [{"mass_kg": 10}],
            "tanks": [{"capacity_m3": 1, "fill_fraction": 1.1, "fluid_density_kg_m3": 1000}],
        }})
        with self.assertRaisesRegex(ValueError, "invalid tank"):
            VesselMassBudgetSolver().solve(request)


class DispatcherIntegrationTests(unittest.TestCase):
    def test_hydrostatics_dispatch(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(CatamaranHydrostaticsSolver())
        request = EngineeringRequest(
            request_id="catamaran-hydro-001", title="Twin hull displacement",
            objective="Estimate displacement at two waterlines",
            geometry=GeometrySpec("catamaran", {"hulls": [hull(), hull()]}),
            operating_conditions={"design_waterline_z_m": 1.0, "maximum_waterline_z_m": 1.5,
                                  "water_density_kg_m3": 1000.0},
        )
        result = dispatcher.dispatch(request, "physics.hydrostatics.catamaran_displacement")
        self.assertAlmostEqual(result.response.values["design_displacement_mass_kg"], 14400.0)

    def test_mass_budget_dispatch(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(VesselMassBudgetSolver())
        request = EngineeringRequest(
            request_id="mass-budget-001", title="Vessel mass ledger",
            objective="Sum component and tank masses",
            operating_conditions={"items": [{"mass_kg": 500, "category": "structure"}],
                                  "tanks": [{"capacity_m3": 1, "fill_fraction": 1,
                                             "fluid_density_kg_m3": 1000}]},
        )
        result = dispatcher.dispatch(request, "physics.vessel.mass_budget")
        self.assertAlmostEqual(result.response.values["total_mass_kg"], 1500.0)


if __name__ == "__main__":
    unittest.main()
