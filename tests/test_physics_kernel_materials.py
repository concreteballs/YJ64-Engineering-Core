import unittest

from yj64_engineering_core.physics.kernel.materials import (
    MaterialLibrary,
    MaterialPropertyEvidence,
    MaterialRecord,
)


class MaterialKernelTests(unittest.TestCase):
    def setUp(self):
        self.modulus = MaterialPropertyEvidence(
            property_name="youngs_modulus",
            value=70e9,
            unit="Pa",
            test_method="ASTM E111",
            source="Example mill certificate / test report",
            source_date="2026-01-15",
            temperature_k=293.15,
            orientation="longitudinal",
            uncertainty_relative=0.03,
        )
        self.record = MaterialRecord(
            material_id="al-5083-h111-plate",
            name="Aluminium alloy 5083",
            family="aluminium_alloy",
            grade="5083",
            product_form="plate",
            condition="H111",
            properties=(self.modulus,),
        )

    def test_material_record_preserves_test_context(self):
        self.assertEqual(self.record.property_evidence("youngs_modulus"), (self.modulus,))
        data = self.record.to_dict()
        self.assertEqual(data["properties"][0]["source"], "Example mill certificate / test report")
        self.assertEqual(data["properties"][0]["orientation"], "longitudinal")

    def test_multiple_values_are_not_silently_collapsed(self):
        transverse = MaterialPropertyEvidence(
            property_name="youngs_modulus",
            value=68e9,
            unit="Pa",
            test_method="ASTM E111",
            source="Second test report",
            orientation="transverse",
        )
        record = MaterialRecord(
            material_id="al-5083-h111-plate-2",
            name="Aluminium alloy 5083",
            family="aluminium_alloy",
            grade="5083",
            product_form="plate",
            condition="H111",
            properties=(self.modulus, transverse),
        )
        self.assertEqual(len(record.property_evidence("youngs_modulus")), 2)

    def test_library_lookup_and_duplicate_protection(self):
        library = MaterialLibrary([self.record])
        self.assertIs(library.get(self.record.material_id), self.record)
        self.assertEqual(library.find_by_family("ALUMINIUM_ALLOY"), (self.record,))
        with self.assertRaisesRegex(ValueError, "already exists"):
            library.add(self.record)

    def test_rejects_invalid_evidence(self):
        with self.assertRaisesRegex(ValueError, "ISO date"):
            MaterialPropertyEvidence(
                property_name="density", value=1000, unit="kg/m3",
                test_method="test", source="report", source_date="15/01/2026",
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            MaterialPropertyEvidence(
                property_name="density", value=1000, unit="kg/m3",
                test_method="test", source="report", uncertainty_relative=-0.1,
            )


if __name__ == "__main__":
    unittest.main()
