import unittest
from yj64_engineering_core.extensions import (CapabilityRequirement,ExtensionCapability,ExtensionDependency,ExtensionManifest,ExtensionRegistry)

def manifest(eid="solver.demo",version="1.0.0",**kw):
    return ExtensionManifest(extension_id=eid,name="Demo solver",version=version,kind="physics_solver",
      capabilities=(ExtensionCapability("fluid.solve","fluid.input/1","fluid.result/1",("SI",),("world",),("UTC",)),),**kw)

class ExtensionRegistryTests(unittest.TestCase):
    def test_manifest_round_trip_and_fingerprint(self):
        item=manifest()
        restored=ExtensionManifest.from_json(item.to_json())
        self.assertEqual(restored,item)
        self.assertEqual(len(item.fingerprint()),64)
    def test_capability_match_checks_schema_units_frame_and_time(self):
        registry=ExtensionRegistry(); registry.register(manifest())
        req=CapabilityRequirement("fluid.solve",("SI",),"world","UTC","fluid.input/1","fluid.result/1")
        self.assertEqual(registry.find_compatible(req),(registry.get("solver.demo"),))
        bad=CapabilityRequirement("fluid.solve",("US customary",),"world","UTC")
        self.assertEqual(registry.find_compatible(bad),())
    def test_rejects_api_mismatch(self):
        registry=ExtensionRegistry()
        with self.assertRaisesRegex(ValueError,"unsupported extension API"):
            registry.register(manifest(api_version="9.0"))
    def test_reports_missing_or_wrong_dependency(self):
        registry=ExtensionRegistry()
        registry.register(manifest("solver.child",dependencies=(ExtensionDependency("solver.base","1.0.0"),)))
        self.assertEqual(registry.validate_dependencies(),{"solver.child":("solver.base",)})
        registry.register(manifest("solver.base","2.0.0"))
        self.assertEqual(registry.validate_dependencies(),{"solver.child":("solver.base",)})
    def test_network_required_cannot_claim_offline(self):
        with self.assertRaisesRegex(ValueError,"cannot claim offline"):
            manifest(network_required=True,offline_supported=True)
    def test_rejects_non_finite_manifest_metadata(self):
        with self.assertRaises(ValueError):
            manifest(resource_requirements={"ram_gb":float("nan")})
    def test_duplicate_registration_rejected(self):
        registry=ExtensionRegistry(); registry.register(manifest())
        with self.assertRaisesRegex(ValueError,"already registered"):
            registry.register(manifest())
if __name__=="__main__": unittest.main()
