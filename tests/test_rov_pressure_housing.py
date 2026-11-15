import math
import unittest

from yj64_engineering_core import (
    EngineeringDispatcher,
    EngineeringRequest,
    GeometrySpec,
    ROVPressureHousingSolver,
)
from yj64_engineering_core.models import AnalysisRequest


def make_analysis_request(**overrides):
    geometry = {
        "outer_diameter_m": 0.20,
        "wall_thickness_m": 0.006,
    }
    conditions = {
        "external_water_depth_m": 20.0,
        "water_density_kg_m3": 1025.0,
        "gravity_m_s2": 9.80665,
        "internal_gauge_pressure_pa": 0.0,
        "buckling_imperfection_factor": 0.30,
        "design_factor_of_safety": 2.0,
    }
    material = {
        "youngs_modulus_pa": 70e9,
        "poisson_ratio": 0.33,
        "allowable_von_mises_stress_pa": 150e6,
    }
    geometry.update(overrides.get("geometry", {}))
    conditions.update(overrides.get("operating_conditions", {}))
    material.update(overrides.get("material", {}))
    return AnalysisRequest(
        "rov.pressure_housing_cylinder_screen",
        {"geometry": geometry, "operating_conditions": conditions, "material": material},
    )


class ROVPressureHousingTests(unittest.TestCase):
    def setUp(self):
        self.solver = ROVPressureHousingSolver()

    def test_hydrostatic_pressure_at_twenty_metres(self):
        result = self.solver.solve(make_analysis_request())
        expected = 1025.0 * 9.80665 * 20.0
        self.assertAlmostEqual(
            result.values["external_hydrostatic_gauge_pressure_pa"], expected
        )
        self.assertAlmostEqual(
            result.values["external_differential_pressure_pa"], expected
        )
        self.assertEqual(result.status, "screening_only")

    def test_membrane_stress_and_end_cap_force(self):
        result = self.solver.solve(make_analysis_request())
        p = 1025.0 * 9.80665 * 20.0
        mean_d = 0.20 - 0.006
        inner_d = 0.20 - 2 * 0.006
        self.assertAlmostEqual(
            result.values["hoop_compressive_stress_pa"], p * mean_d / (2 * 0.006)
        )
        self.assertAlmostEqual(
            result.values["axial_compressive_stress_pa"], p * mean_d / (4 * 0.006)
        )
        self.assertAlmostEqual(
            result.values["end_cap_resultant_force_n"],
            p * math.pi * inner_d**2 / 4,
        )

    def test_internal_gauge_pressure_reduces_external_differential(self):
        baseline = self.solver.solve(make_analysis_request())
        pressurized = self.solver.solve(make_analysis_request(
            operating_conditions={"internal_gauge_pressure_pa": 50_000.0}
        ))
        self.assertAlmostEqual(
            baseline.values["external_differential_pressure_pa"]
            - pressurized.values["external_differential_pressure_pa"],
            50_000.0,
        )

    def test_thick_wall_rejected_by_thin_wall_model(self):
        with self.assertRaisesRegex(ValueError, "thin-wall screening"):
            self.solver.solve(make_analysis_request(
                geometry={"wall_thickness_m": 0.025}
            ))

    def test_nonpositive_external_differential_rejected(self):
        with self.assertRaisesRegex(ValueError, "external differential pressure"):
            self.solver.solve(make_analysis_request(
                operating_conditions={"internal_gauge_pressure_pa": 250_000.0}
            ))

    def test_buckling_factor_is_required_and_bounded(self):
        with self.assertRaisesRegex(TypeError, "buckling_imperfection_factor"):
            self.solver.solve(make_analysis_request(
                operating_conditions={"buckling_imperfection_factor": None}
            ))
        with self.assertRaisesRegex(ValueError, "must be <= 1.0"):
            self.solver.solve(make_analysis_request(
                operating_conditions={"buckling_imperfection_factor": 1.1}
            ))

    def test_invalid_poisson_ratio_rejected(self):
        with self.assertRaisesRegex(ValueError, "poisson_ratio"):
            self.solver.solve(make_analysis_request(
                material={"poisson_ratio": 0.5}
            ))

    def test_dispatcher_integration_and_provenance(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(self.solver)
        request = EngineeringRequest(
            request_id="rov-pressure-001",
            title="ROV cylindrical pressure housing",
            objective="Screen external hydrostatic pressure at 20 m depth",
            geometry=GeometrySpec(
                "cylindrical_pressure_housing",
                {"outer_diameter_m": 0.20, "wall_thickness_m": 0.006},
            ),
            material={
                "name": "Example isotropic material",
                "youngs_modulus_pa": 70e9,
                "poisson_ratio": 0.33,
                "allowable_von_mises_stress_pa": 150e6,
            },
            operating_conditions={
                "external_water_depth_m": 20.0,
                "water_density_kg_m3": 1025.0,
                "gravity_m_s2": 9.80665,
                "internal_gauge_pressure_pa": 0.0,
                "buckling_imperfection_factor": 0.30,
                "design_factor_of_safety": 2.0,
            },
        )
        dispatched = dispatcher.dispatch(
            request, "physics.rov.pressure_housing_cylinder_screen"
        )
        self.assertEqual(dispatched.response.status, "screening_only")
        self.assertEqual(dispatched.response.request_id, "rov-pressure-001")
        self.assertEqual(len(dispatched.response.provenance.input_digest_sha256), 64)
        self.assertGreater(
            dispatched.response.values["ideal_long_cylinder_elastic_buckling_pressure_pa"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
