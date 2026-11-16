import unittest

from yj64_engineering_core.physics.kernel.quantities import Quantity
from yj64_engineering_core.physics.kernel.unit_profiles import (
    BUILTIN_UNIT_PROFILES, DocumentUnitPolicy, UnitDisplayPreferences,
    US_CUSTOMARY_PROFILE, UK_IMPERIAL_PROFILE, MARINE_HYBRID_PROFILE, NominalSizeDesignation,
    parse_voice_unit_command, convert_by_voice,
)


class UnitProfileTests(unittest.TestCase):
    def test_builtin_profiles_exist(self):
        self.assertIn("us_customary", BUILTIN_UNIT_PROFILES)
        self.assertIn("european_metric", BUILTIN_UNIT_PROFILES)
        self.assertIn("uk_imperial", BUILTIN_UNIT_PROFILES)
        self.assertEqual(UK_IMPERIAL_PROFILE.defaults[(0, 3, 0, 0, 0, 0, 0)], "Imp_gal")
        self.assertEqual(DocumentUnitPolicy.ASK.value, "ask")

    def test_field_override_supports_hybrid_units(self):
        prefs = UnitDisplayPreferences(
            MARINE_HYBRID_PROFILE,
            {"plumbing.nominal_pipe_diameter": "in",
             "plumbing.wall_penetration_hole_diameter": "mm"},
        )
        self.assertAlmostEqual(prefs.display(
            "plumbing.nominal_pipe_diameter", Quantity(25.4, "mm")
        ).value, 1.0)
        self.assertAlmostEqual(prefs.display(
            "plumbing.wall_penetration_hole_diameter", Quantity(1.0, "in")
        ).value, 25.4)

    def test_wrong_dimension_override_is_rejected_when_used(self):
        prefs = UnitDisplayPreferences(
            US_CUSTOMARY_PROFILE, {"frame.length": "lb"}
        )
        with self.assertRaisesRegex(ValueError, "incompatible dimensions"):
            prefs.display("frame.length", Quantity(1, "m"))

    def test_voice_russian_inches_to_centimeters(self):
        command = parse_voice_unit_command("Переведи дюймы в сантиметры")
        result = convert_by_voice(Quantity(2, "in"), command)
        self.assertAlmostEqual(result.value, 5.08)

    def test_voice_english_kilograms_to_pounds(self):
        command = parse_voice_unit_command("convert kilograms to pounds")
        result = convert_by_voice(Quantity(10, "kg"), command)
        self.assertAlmostEqual(result.value, 22.0462262185, places=6)

    def test_voice_command_can_target_a_specific_parameter(self):
        command = parse_voice_unit_command("переведи дюймы в миллиметры для диаметра отверстия")
        self.assertEqual(command.field_key, "диаметра.отверстия")

    def test_nominal_pipe_size_is_not_an_arithmetic_length(self):
        pipe = NominalSizeDesignation("NPS", "1", "ASME B36.10M", Quantity(33.4, "mm"))
        self.assertEqual(pipe.designation, "1")
        self.assertAlmostEqual(pipe.actual_outside_diameter.to("in").value, 1.3149606299)
        with self.assertRaisesRegex(ValueError, "length dimension"):
            NominalSizeDesignation("NPS", "1", "ASME B36.10M", Quantity(2, "kg"))

    def test_voice_rejects_dimension_mismatch(self):
        with self.assertRaisesRegex(ValueError, "incompatible dimensions"):
            parse_voice_unit_command("переведи килограммы в сантиметры")

    def test_voice_rejects_ambiguous_or_unknown_terms(self):
        with self.assertRaises(ValueError):
            parse_voice_unit_command("сделай побольше")
        with self.assertRaisesRegex(ValueError, "not recognized"):
            parse_voice_unit_command("переведи шланги в трубы")


if __name__ == "__main__":
    unittest.main()
