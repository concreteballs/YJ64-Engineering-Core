import math
import unittest

from yj64_engineering_core.physics.kernel.quantities import (
    DEFAULT_UNIT_REGISTRY,
    DIMENSIONLESS,
    LENGTH,
    Quantity,
    UnitDefinition,
    UnitRegistry,
)


class QuantityKernelTests(unittest.TestCase):
    def test_length_conversion(self):
        result = Quantity(2.5, "m").to("mm")
        self.assertAlmostEqual(result.value, 2500.0)
        self.assertEqual(result.dimension, LENGTH)

    def test_force_and_pressure_prefixes(self):
        self.assertAlmostEqual(Quantity(3.2, "kN").to("N").value, 3200.0)
        self.assertAlmostEqual(Quantity(1.7, "MPa").to("kPa").value, 1700.0)

    def test_temperature_offset_conversion(self):
        self.assertAlmostEqual(Quantity(0.0, "degC").to("K").value, 273.15)
        self.assertAlmostEqual(Quantity(293.15, "K").to("degC").value, 20.0)

    def test_angle_conversion(self):
        self.assertAlmostEqual(Quantity(180.0, "deg").to("rad").value, math.pi)

    def test_rejects_dimension_mismatch(self):
        with self.assertRaisesRegex(ValueError, "incompatible dimensions"):
            Quantity(1.0, "m").to("s")

    def test_rejects_non_finite_and_boolean_values(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            Quantity(float("nan"), "m")
        with self.assertRaisesRegex(TypeError, "real number"):
            Quantity(True, "m")

    def test_unknown_units_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown unit"):
            Quantity(1.0, "furlong")

    def test_registry_is_extensible_and_rejects_duplicates(self):
        registry = UnitRegistry([UnitDefinition("widget", DIMENSIONLESS, 2.0)])
        self.assertAlmostEqual(Quantity(3.0, "widget", registry).si_value, 6.0)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(UnitDefinition("widget", DIMENSIONLESS))
        self.assertIn("kg/m3", DEFAULT_UNIT_REGISTRY.symbols())

    def test_serialization_retains_unit_and_dimension(self):
        data = Quantity(1025.0, "kg/m3").to_dict()
        self.assertEqual(data["unit"], "kg/m3")
        self.assertEqual(data["dimension"], [1, -3, 0, 0, 0, 0, 0])
        self.assertAlmostEqual(data["si_value"], 1025.0)


if __name__ == "__main__":
    unittest.main()
