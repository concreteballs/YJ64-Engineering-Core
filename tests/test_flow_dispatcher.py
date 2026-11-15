import unittest

from yj64_engineering_core import (
    AerodynamicsSolver,
    EngineeringDispatcher,
    EngineeringRequest,
    GeometrySpec,
    HydrodynamicsSolver,
)


class FlowDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EngineeringDispatcher()
        self.dispatcher.register_physics_solver(AerodynamicsSolver())
        self.dispatcher.register_physics_solver(HydrodynamicsSolver())

    def make_request(self, request_id, density):
        return EngineeringRequest(
            request_id=request_id,
            title="Coefficient flow screening",
            objective="Route a preliminary flow force estimate",
            geometry=GeometrySpec(
                "reference_surface",
                {"reference_area_m2": 12.0, "characteristic_length_m": 3.0},
            ),
            operating_conditions={
                "flow_speed_m_s": 8.0,
                "fluid_density_kg_m3": density,
                "dynamic_viscosity_pa_s": 1.8e-5 if density < 10 else 1.05e-3,
                "lift_coefficient": 0.8,
                "drag_coefficient": 0.12,
                "side_force_coefficient": 0.1,
            },
        )

    def test_dispatches_aerodynamic_analysis(self):
        result = self.dispatcher.dispatch(
            self.make_request("aero-route-001", 1.225),
            "physics.aerodynamics.coefficient_forces",
        )
        self.assertEqual(result.response.status, "screening_only")
        self.assertAlmostEqual(result.response.values["dynamic_pressure_pa"], 39.2)
        self.assertEqual(result.response.provenance.solver_name, AerodynamicsSolver.name)

    def test_dispatches_hydrodynamic_analysis(self):
        result = self.dispatcher.dispatch(
            self.make_request("hydro-route-001", 1025.0),
            "physics.hydrodynamics.coefficient_forces",
        )
        self.assertEqual(result.response.status, "screening_only")
        self.assertAlmostEqual(result.response.values["dynamic_pressure_pa"], 32800.0)
        self.assertEqual(result.response.provenance.solver_name, HydrodynamicsSolver.name)


if __name__ == "__main__":
    unittest.main()
