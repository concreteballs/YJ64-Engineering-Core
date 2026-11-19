import json
import unittest
from pathlib import Path

from yj64_engineering_core.extensions import (
    CapabilityRequirement, ExtensionManifest, ExtensionRegistry,
)


FIXTURES = Path(__file__).parent / "fixtures" / "cross_module"


class DisciplinePackManifestTests(unittest.TestCase):
    def test_both_published_manifests_parse_and_register_in_isolated_registry(self):
        registry = ExtensionRegistry()
        manifests = []
        for filename in ("biological-engineering.json", "molecular-genetic-engineering.json"):
            source = (FIXTURES / filename).read_text(encoding="utf-8")
            manifest = ExtensionManifest.from_json(source)
            manifests.append(manifest)
            registry.register(manifest)

        self.assertEqual(len(registry.manifests), 2)
        self.assertEqual(registry.validate_dependencies(), {})
        for manifest in manifests:
            self.assertEqual(manifest.permissions, ())
            self.assertFalse(manifest.network_required)
            self.assertTrue(manifest.offline_supported)
            self.assertEqual(manifest.kind, "discipline_pack")
            self.assertEqual(
                {cap.operation for cap in manifest.capabilities},
                {"review_candidate", "contribute_enhancements"},
            )

    def test_review_and_contribution_contracts_are_discoverable(self):
        registry = ExtensionRegistry()
        for filename in ("biological-engineering.json", "molecular-genetic-engineering.json"):
            manifest = ExtensionManifest.from_json(
                (FIXTURES / filename).read_text(encoding="utf-8")
            )
            registry.register(manifest)

        review = CapabilityRequirement(
            operation="review_candidate",
            input_schema="yj64.cross_module.candidate.v1",
            output_schema="yj64.cross_module.review.v1",
        )
        contribution = CapabilityRequirement(
            operation="contribute_enhancements",
            input_schema="yj64.cross_module.candidate.v1",
            output_schema="yj64.cross_module.contribution.v1",
        )
        self.assertEqual(len(registry.find_compatible(review)), 2)
        self.assertEqual(len(registry.find_compatible(contribution)), 2)


if __name__ == "__main__":
    unittest.main()
