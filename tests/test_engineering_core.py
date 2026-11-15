import math
import unittest

from yj64_engineering_core.cad.openscad import cylinder_scad
from yj64_engineering_core.models import MaterialProperties
from yj64_engineering_core.physics.statics import calculate_axial_member


class AxialMemberTests(unittest.TestCase):
    def setUp(self):
        self.steel = MaterialProperties(
            name="Example steel",
            youngs_modulus_pa=200e9,
            allowable_stress_pa=250e6,
            density_kg_m3=7850,
        )

    def test_axial_stress_and_elongation(self):
        result = calculate_axial_member(
            force_n=10_000,
            area_m2=1e-4,
            length_m=1.0,
            material=self.steel,
        )
        self.assertEqual(result.status, "screening_only")
        self.assertAlmostEqual(result.values["stress_pa"], 100e6)
        self.assertAlmostEqual(result.values["elongation_m"], 0.0005)
        self.assertAlmostEqual(result.values["safety_factor_vs_allowable"], 2.5)

    def test_over_allowable_stress_is_flagged(self):
        result = calculate_axial_member(
            force_n=30_000,
            area_m2=1e-4,
            length_m=1.0,
            material=self.steel,
        )
        self.assertEqual(result.status, "fail_screening")
        self.assertTrue(result.warnings)

    def test_zero_force_has_infinite_safety_factor(self):
        result = calculate_axial_member(
            force_n=0,
            area_m2=1e-4,
            length_m=1.0,
            material=self.steel,
        )
        self.assertTrue(math.isinf(result.values["safety_factor_vs_allowable"]))

    def test_invalid_area_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_axial_member(
                force_n=100,
                area_m2=0,
                length_m=1.0,
                material=self.steel,
            )


class OpenScadTests(unittest.TestCase):
    def test_cylinder_source_is_generated(self):
        source = cylinder_scad(radius_mm=10, height_mm=20)
        self.assertIn("cylinder(h = height, r = radius, center = true);", source)
        self.assertIn("radius = 10.000000", source)

    def test_invalid_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            cylinder_scad(radius_mm=-1, height_mm=20)


if __name__ == "__main__":
    unittest.main()
