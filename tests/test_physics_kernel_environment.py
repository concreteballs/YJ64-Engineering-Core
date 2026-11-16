import unittest

from yj64_engineering_core.physics.kernel.environment import (
    dry_air_density_ideal_kg_m3,
    seawater_density_eos80_kg_m3,
)


class EnvironmentKernelTests(unittest.TestCase):
    def test_standard_dry_air_reference_state(self):
        result = dry_air_density_ideal_kg_m3(288.15, 101325.0)
        self.assertAlmostEqual(result.density_kg_m3, 1.225, places=3)
        self.assertEqual(result.model, "ideal_dry_air")

    def test_seawater_reference_state(self):
        result = seawater_density_eos80_kg_m3(15.0, 35.0)
        self.assertAlmostEqual(result.density_kg_m3, 1025.9728, places=3)
        self.assertEqual(result.model, "UNESCO_1983_EOS80_atmospheric_pressure")

    def test_pure_water_reference_state(self):
        result = seawater_density_eos80_kg_m3(15.0, 0.0)
        self.assertAlmostEqual(result.density_kg_m3, 999.1016, places=3)

    def test_rejects_out_of_range_inputs(self):
        with self.assertRaisesRegex(ValueError, "0..40"):
            seawater_density_eos80_kg_m3(45.0, 35.0)
        with self.assertRaisesRegex(ValueError, "30000..120000"):
            dry_air_density_ideal_kg_m3(288.15, 150000.0)


if __name__ == "__main__":
    unittest.main()
