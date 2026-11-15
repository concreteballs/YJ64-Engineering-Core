import math
import unittest

from yj64_engineering_core import (
    EngineeringDispatcher, EngineeringRequest, GeometrySpec,
    VesselMotionKinematicsSolver,
)
from yj64_engineering_core.models import AnalysisRequest


class VesselMotionKinematicsTests(unittest.TestCase):
    def setUp(self):
        self.solver = VesselMotionKinematicsSolver()

    def request(self, point=(1.0, 0.0, 0.0), conditions=None):
        return AnalysisRequest(
            "marine.vessel_motion_point_kinematics",
            {
                "geometry": {"point_body_m": list(point)},
                "operating_conditions": conditions or {},
            },
        )

    def test_static_point_translation(self):
        result = self.solver.solve(self.request(
            point=(1, 2, 3),
            conditions={"vessel_position_xyz_m": [10, 20, 30]},
        ))
        self.assertEqual(result.values["point_position_earth_xyz_m"], [11, 22, 33])
        self.assertEqual(result.values["point_velocity_earth_xyz_m_s"], [0, 0, 0])
        self.assertEqual(result.values["point_acceleration_earth_xyz_m_s2"], [0, 0, 0])

    def test_yaw_rotation_transforms_point(self):
        result = self.solver.solve(self.request(
            point=(1, 0, 0),
            conditions={"orientation_rpy_rad": [0, 0, math.pi / 2]},
        ))
        p = result.values["point_position_earth_xyz_m"]
        self.assertAlmostEqual(p[0], 0.0, places=9)
        self.assertAlmostEqual(p[1], 1.0, places=9)
        self.assertAlmostEqual(p[2], 0.0, places=9)

    def test_rotational_velocity_and_centripetal_acceleration(self):
        result = self.solver.solve(self.request(
            point=(2, 0, 0),
            conditions={"angular_velocity_body_xyz_rad_s": [0, 0, 3]},
        ))
        self.assertEqual(result.values["point_velocity_earth_xyz_m_s"], [0.0, 6.0, 0.0])
        self.assertEqual(result.values["point_acceleration_earth_xyz_m_s2"], [-18.0, 0.0, 0.0])

    def test_angular_acceleration_contribution(self):
        result = self.solver.solve(self.request(
            point=(2, 0, 0),
            conditions={"angular_acceleration_body_xyz_rad_s2": [0, 0, 4]},
        ))
        self.assertEqual(result.values["point_acceleration_earth_xyz_m_s2"], [0.0, 8.0, 0.0])

    def test_translational_and_rotational_terms_add(self):
        result = self.solver.solve(self.request(
            point=(1, 0, 0),
            conditions={
                "linear_velocity_xyz_m_s": [1, 2, 3],
                "linear_acceleration_xyz_m_s2": [4, 5, 6],
                "angular_velocity_body_xyz_rad_s": [0, 0, 2],
                "angular_acceleration_body_xyz_rad_s2": [0, 0, 3],
            },
        ))
        self.assertEqual(result.values["point_velocity_earth_xyz_m_s"], [1.0, 4.0, 3.0])
        self.assertEqual(result.values["point_acceleration_earth_xyz_m_s2"], [0.0, 8.0, 6.0])

    def test_invalid_vector_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly three"):
            self.solver.solve(self.request(conditions={"orientation_rpy_rad": [0, 1]}))
        with self.assertRaisesRegex(ValueError, "finite"):
            self.solver.solve(self.request(conditions={"linear_velocity_xyz_m_s": [0, float("nan"), 0]}))

    def test_dispatcher_integration(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_physics_solver(self.solver)
        request = EngineeringRequest(
            request_id="vessel-motion-001",
            title="Deck point motion",
            objective="Transform equipment point kinematics from vessel motion",
            geometry=GeometrySpec("body_fixed_point", {"point_body_m": [1, 0, 0]}),
            operating_conditions={"angular_velocity_body_xyz_rad_s": [0, 0, 1]},
        )
        response = dispatcher.dispatch(
            request, "physics.marine.vessel_motion_point_kinematics"
        ).response
        self.assertEqual(response.status, "screening_only")
        self.assertAlmostEqual(response.values["point_velocity_earth_xyz_m_s"][1], 1.0)
        self.assertEqual(len(response.provenance.input_digest_sha256), 64)


if __name__ == "__main__":
    unittest.main()
