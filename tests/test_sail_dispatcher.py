import unittest

from yj64_engineering_core import EngineeringDispatcher, EngineeringRequest, GeometrySpec, SailAerodynamicsSolver


class SailPolarDispatcherTests(unittest.TestCase):
    def test_routes_sail_polar_operation(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(SailAerodynamicsSolver())
        request = EngineeringRequest(
            request_id="sail-polar-route-001",
            title="Sail polar route test",
            objective="Check sail force routing through the shared engineering dispatcher",
            geometry=GeometrySpec(
                "sail",
                {
                    "sail_area_m2": 30.0,
                    "span_m": 12.0,
                    "mean_chord_m": 2.5,
                    "polar_source": "dispatcher test data",
                    "polar_points": [
                        {"alpha_deg": -5.0, "cl": -0.2, "cd": 0.05, "cm": 0.01},
                        {"alpha_deg": 5.0, "cl": 0.6, "cd": 0.04, "cm": -0.02},
                        {"alpha_deg": 15.0, "cl": 1.0, "cd": 0.09, "cm": -0.06},
                    ],
                },
            ),
            operating_conditions={
                "apparent_wind_speed_m_s": 9.0,
                "air_density_kg_m3": 1.225,
                "dynamic_viscosity_pa_s": 1.81e-5,
                "angle_of_attack_deg": 5.0,
                "apparent_wind_from_angle_deg": 50.0,
                "oswald_efficiency": 0.82,
            },
        )
        result = dispatcher.dispatch(request, "physics.aerodynamics.sail_polar")
        self.assertEqual(result.operation, "physics.aerodynamics.sail_polar")
        self.assertEqual(result.response.status, "screening_only")
        self.assertEqual(result.response.provenance.solver_name, SailAerodynamicsSolver.name)
        self.assertGreater(result.response.values["lift_force_n"], 0.0)


if __name__ == "__main__":
    unittest.main()
