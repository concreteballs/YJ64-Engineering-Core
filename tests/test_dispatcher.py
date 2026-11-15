import unittest

from yj64_engineering_core.contracts import EngineeringRequest, GeometrySpec, LoadCase
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher


class DummyCADBackend:
    name = "dummy-cad"
    version = "1.2"

    def generate(self, specification):
        self.last_specification = specification
        return {
            "format": "application/step",
            "location": "workspace://part.step",
            "warnings": ["Dummy backend: no real geometry generated"],
            "limitations": ["Test double only"],
        }


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EngineeringDispatcher()
        self.dispatcher.register_physics_solver(AxialMemberSolver())

    def make_axial_request(self, force_n=1000.0):
        return EngineeringRequest(
            request_id="bar-test-001",
            title="Axial bar screening",
            objective="Calculate preliminary axial stress and elongation",
            geometry=GeometrySpec(
                geometry_type="prismatic_member",
                parameters={"area_m2": 0.001, "length_m": 2.0},
            ),
            material={
                "name": "Test steel",
                "youngs_modulus_pa": 200e9,
                "allowable_stress_pa": 150e6,
            },
            load_cases=(LoadCase(name="service", force_n=(0.0, 0.0, force_n)),),
        )

    def test_dispatches_axial_request_to_real_reference_solver(self):
        dispatched = self.dispatcher.dispatch(
            self.make_axial_request(), "physics.axial_member"
        )
        self.assertEqual(dispatched.response.status, "screening_only")
        self.assertEqual(dispatched.response.values["stress_pa"], 1e6)
        self.assertEqual(dispatched.response.provenance.method, "linear_elastic_axial_stress")
        self.assertEqual(dispatched.response.request_id, "bar-test-001")

    def test_axial_adapter_rejects_transverse_force(self):
        request = EngineeringRequest(
            request_id="bar-test-002",
            title="Invalid axial case",
            objective="Check unsupported transverse load",
            geometry=GeometrySpec(
                geometry_type="bar",
                parameters={"area_m2": 0.001, "length_m": 1.0},
            ),
            material={
                "name": "Test steel",
                "youngs_modulus_pa": 200e9,
                "allowable_stress_pa": 150e6,
            },
            load_cases=(LoadCase(name="service", force_n=(10.0, 0.0, 100.0)),),
        )
        with self.assertRaisesRegex(ValueError, "Z-axis axial force"):
            self.dispatcher.dispatch(request, "physics.axial_member")

    def test_unknown_operation_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported operation"):
            self.dispatcher.dispatch(self.make_axial_request(), "auto")

    def test_missing_solver_fails_explicitly(self):
        with self.assertRaisesRegex(LookupError, "No registered solver"):
            self.dispatcher.dispatch(self.make_axial_request(), "physics.cfd")

    def test_dispatches_to_registered_cad_backend(self):
        backend = DummyCADBackend()
        self.dispatcher.register_cad_backend("dummy", backend)
        request = EngineeringRequest(
            request_id="cad-test-001",
            title="Cylinder CAD",
            objective="Generate a CAD artifact",
            geometry=GeometrySpec("cylinder", {"diameter_m": 0.1, "height_m": 0.2}),
            operating_conditions={"cad_backend": "dummy"},
        )
        dispatched = self.dispatcher.dispatch(request, "cad.generate")
        self.assertEqual(dispatched.response.status, "completed")
        self.assertEqual(backend.last_specification["geometry_type"], "cylinder")
        self.assertIn("Test double", dispatched.response.limitations[0])
        self.assertEqual(dispatched.response.artifacts[0].uri, "workspace://part.step")
        self.assertEqual(dispatched.response.artifacts[0].media_type, "application/step")

    def test_cad_requires_explicit_backend(self):
        request = EngineeringRequest(
            request_id="cad-test-002",
            title="Cylinder CAD",
            objective="Generate a CAD artifact",
            geometry=GeometrySpec("cylinder", {"diameter_m": 0.1, "height_m": 0.2}),
        )
        with self.assertRaisesRegex(ValueError, "cad_backend"):
            self.dispatcher.dispatch(request, "cad.generate")


if __name__ == "__main__":
    unittest.main()
