import unittest

from yj64_engineering_core.component_model import (
    ComponentCalculationRecord,
    ComponentDependency,
    ComponentInterface,
    ComponentMassProperties,
    EngineeringComponent,
    EvidenceRecord,
    ManufacturingConstraint,
    stale_calculations,
    stale_component_dependencies,
)
from yj64_engineering_core.contracts import GeometrySpec


class EngineeringComponentTests(unittest.TestCase):
    def make_component(self, **overrides):
        values = {
            "component_id": "hull.port.shell",
            "revision": 1,
            "name": "Port hull shell",
            "component_type": "structural_shell",
            "geometry": GeometrySpec("surface", {"area_m2": 42.0}),
            "material": {"family": "glass_fiber_composite", "density_kg_m3": 1850.0},
            "mass_properties": ComponentMassProperties(
                125.0,
                (4.2, -2.1, 0.8),
                ((10.0, 0.0, 0.0), (0.0, 12.0, 0.0), (0.0, 0.0, 15.0)),
            ),
            "interfaces": (ComponentInterface("crossbeam_joint", "bolted_joint"),),
            "manufacturing_constraints": (
                ManufacturingConstraint("vacuum_infusion", {"max_layup_thickness_m": 0.025}),
            ),
            "evidence": (
                EvidenceRecord("laminate-spec", "material_datasheet", "Supplier laminate data"),
            ),
        }
        values.update(overrides)
        return EngineeringComponent(**values)

    def test_component_is_json_serializable_and_fingerprinted(self):
        component = self.make_component()
        self.assertIn('"component_id": "hull.port.shell"', component.to_json())
        self.assertEqual(len(component.fingerprint()), 64)
        self.assertEqual(component.fingerprint(), self.make_component().fingerprint())

    def test_revision_changes_fingerprint(self):
        first = self.make_component()
        second = self.make_component(revision=2)
        self.assertNotEqual(first.fingerprint(), second.fingerprint())

    def test_dependency_invalidation_detects_changed_and_missing_revisions(self):
        consumer = self.make_component(
            component_id="crossbeam.port",
            dependencies=(
                ComponentDependency("hull.port.shell", 1, "joint geometry"),
                ComponentDependency("deck.panel", 3, "interface layout"),
            ),
        )
        stale = stale_component_dependencies([consumer], {"hull.port.shell": 2})
        self.assertEqual(stale, {
            "crossbeam.port": ("hull.port.shell", "deck.panel")
        })

    def test_current_dependency_is_not_stale(self):
        consumer = self.make_component(
            component_id="crossbeam.port",
            dependencies=(ComponentDependency("hull.port.shell", 1, "joint geometry"),),
        )
        self.assertEqual(
            stale_component_dependencies([consumer], {"hull.port.shell": 1}), {}
        )

    def test_rejects_fractional_revision_numbers(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.make_component(revision=1.5)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            ComponentDependency("mast", 2.5, "attachment")

    def test_rejects_non_integer_current_revision_map(self):
        component = self.make_component(
            component_id="crossbeam",
            dependencies=(ComponentDependency("hull.port.shell", 1, "joint"),),
        )
        with self.assertRaisesRegex(ValueError, "positive integer revisions"):
            stale_component_dependencies([component], {"hull.port.shell": 1.5})


    def test_calculation_record_pins_component_revisions(self):
        record = ComponentCalculationRecord(
            calculation_id="calc.foil-root.loadcase-a",
            operation="physics.axial_member",
            input_digest_sha256="a" * 64,
            component_dependencies=(
                ComponentDependency("foil.root", 2, "geometry and material"),
                ComponentDependency("crossbeam.main", 4, "attachment stiffness"),
            ),
            result_digest_sha256="b" * 64,
            artifact_ids=("report.foil-root",),
        )
        self.assertEqual(len(record.fingerprint()), 64)
        self.assertEqual(stale_calculations([record], {
            "foil.root": 3,
            "crossbeam.main": 4,
        }), {"calc.foil-root.loadcase-a": ("foil.root",)})

    def test_calculation_is_stale_when_dependency_is_missing(self):
        record = ComponentCalculationRecord(
            calculation_id="calc.hull.shell",
            operation="physics.shell_fem",
            input_digest_sha256="c" * 64,
            component_dependencies=(
                ComponentDependency("hull.port.shell", 1, "mesh source"),
            ),
        )
        self.assertEqual(
            stale_calculations([record], {}),
            {"calc.hull.shell": ("hull.port.shell",)},
        )

    def test_current_calculation_dependencies_are_not_stale(self):
        record = ComponentCalculationRecord(
            calculation_id="calc.hull.shell",
            operation="physics.shell_fem",
            input_digest_sha256="d" * 64,
            component_dependencies=(
                ComponentDependency("hull.port.shell", 1, "mesh source"),
            ),
        )
        self.assertEqual(
            stale_calculations([record], {"hull.port.shell": 1}), {}
        )

    def test_calculation_record_rejects_invalid_digest(self):
        with self.assertRaisesRegex(ValueError, "input_digest_sha256"):
            ComponentCalculationRecord(
                calculation_id="calc.invalid",
                operation="physics.test",
                input_digest_sha256="not-a-digest",
                component_dependencies=(),
            )

    def test_rejects_non_finite_material_data(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            self.make_component(material={"density_kg_m3": float("nan")})

    def test_rejects_non_symmetric_inertia_tensor(self):
        with self.assertRaisesRegex(ValueError, "symmetric"):
            ComponentMassProperties(
                10.0, inertia_tensor_kg_m2=((1, 2, 0), (0, 1, 0), (0, 0, 1))
            )

    def test_rejects_self_dependency(self):
        with self.assertRaisesRegex(ValueError, "depend on itself"):
            self.make_component(
                dependencies=(ComponentDependency("hull.port.shell", 1, "invalid"),)
            )

    def test_rejects_unknown_lifecycle_state(self):
        with self.assertRaisesRegex(ValueError, "lifecycle_state"):
            self.make_component(lifecycle_state="certified_by_ai")


if __name__ == "__main__":
    unittest.main()
