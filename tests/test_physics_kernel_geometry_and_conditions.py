import unittest

from yj64_engineering_core.physics.kernel.coordinate_frames import (
    CoordinateFrame, CoordinateFrameRegistry, RigidTransform,
)
from yj64_engineering_core.physics.kernel.geometry import (
    AxisAlignedBoundingBox, Cylinder, GeometryPoint, GeometryVector,
    LineSegment, Plane, Sphere,
)
from yj64_engineering_core.physics.kernel.conditions import AppliedLoad, BoundaryCondition
from yj64_engineering_core.physics.kernel.quantities import Quantity


class CoordinateFrameTests(unittest.TestCase):
    def test_transform_and_inverse(self):
        rotation_z_90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        transform = RigidTransform("part", "world", rotation_z_90, (10.0, 0.0, 0.0))
        point = transform.apply_point((1.0, 0.0, 0.0))
        self.assertAlmostEqual(point[0], 10.0)
        self.assertAlmostEqual(point[1], 1.0)
        recovered = transform.inverse().apply_point(point)
        self.assertAlmostEqual(recovered[0], 1.0)
        self.assertAlmostEqual(recovered[1], 0.0)

    def test_registry_transforms_between_nested_frames(self):
        registry = CoordinateFrameRegistry()
        registry.add(CoordinateFrame("world"))
        registry.add(CoordinateFrame("deck", "world", translation_to_parent_m=(2, 0, 0)))
        registry.add(CoordinateFrame("sensor", "deck", translation_to_parent_m=(0, 3, 0)))
        result = registry.transform("sensor", "world").apply_point((0, 0, 0))
        self.assertEqual(result, (2.0, 3.0, 0.0))
        back = registry.transform("world", "sensor").apply_point(result)
        self.assertAlmostEqual(back[0], 0.0)
        self.assertAlmostEqual(back[1], 0.0)

    def test_rejects_reflection_and_non_orthogonal_rotation(self):
        with self.assertRaisesRegex(ValueError, "determinant"):
            RigidTransform("a", "b", ((-1,0,0),(0,1,0),(0,0,1)))
        with self.assertRaisesRegex(ValueError, "orthonormal"):
            RigidTransform("a", "b", ((1,0,0),(0,2,0),(0,0,1)))

    def test_registry_requires_existing_parent_and_one_identity_root(self):
        registry = CoordinateFrameRegistry()
        with self.assertRaisesRegex(ValueError, "not registered"):
            registry.add(CoordinateFrame("child", "missing"))
        with self.assertRaisesRegex(ValueError, "identity world pose"):
            registry.add(CoordinateFrame("shifted", translation_to_parent_m=(1, 0, 0)))
        registry.add(CoordinateFrame("world"))
        with self.assertRaisesRegex(ValueError, "one root"):
            registry.add(CoordinateFrame("other"))


class GeometryPrimitiveTests(unittest.TestCase):
    def test_geometry_primitives(self):
        a = GeometryPoint(0, 0, 0)
        b = GeometryPoint(3, 4, 0)
        self.assertEqual(LineSegment(a, b).length_m, 5.0)
        self.assertAlmostEqual(GeometryVector(0, 3, 4).normalized().magnitude, 1.0)
        self.assertEqual(Plane(a, GeometryVector(0, 0, 1)).normal.z, 1)
        box = AxisAlignedBoundingBox(a, b)
        self.assertEqual(box.dimensions_m, (3.0, 4.0, 0.0))
        self.assertEqual(Sphere(a, 2).radius_m, 2)
        self.assertEqual(Cylinder(a, b, 0.5).radius_m, 0.5)

    def test_rejects_mixed_frames_and_degenerate_geometry(self):
        with self.assertRaisesRegex(ValueError, "same coordinate frame"):
            LineSegment(GeometryPoint(0,0,0,"a"), GeometryPoint(1,0,0,"b"))
        with self.assertRaisesRegex(ValueError, "positive"):
            LineSegment(GeometryPoint(0,0,0), GeometryPoint(0,0,0))
        with self.assertRaisesRegex(ValueError, "unit vector"):
            Plane(GeometryPoint(0,0,0), GeometryVector(0,0,2))


class TypedLoadAndBoundaryTests(unittest.TestCase):
    def test_force_and_moment_loads(self):
        force = AppliedLoad(
            "L1", "hull.panel.1", "force",
            (Quantity(1,"N"), Quantity(2,"N"), Quantity(3,"kN")),
            "world", application_point=GeometryPoint(0,0,0),
        )
        self.assertEqual(force.kind, "force")
        moment = AppliedLoad(
            "L2", "mast.base", "moment",
            (Quantity(1,"N*m"), Quantity(0,"N*m"), Quantity(0,"N*m")),
            "world",
        )
        self.assertEqual(moment.components[0].si_value, 1.0)

    def test_rejects_wrong_load_dimension_and_frame(self):
        with self.assertRaisesRegex(ValueError, "dimension"):
            AppliedLoad(
                "L", "part", "force",
                (Quantity(1,"Pa"), Quantity(0,"N"), Quantity(0,"N")), "world",
            )
        with self.assertRaisesRegex(ValueError, "load coordinate frame"):
            AppliedLoad(
                "L", "part", "force",
                (Quantity(1,"N"), Quantity(0,"N"), Quantity(0,"N")), "world",
                application_point=GeometryPoint(0,0,0,"deck"),
            )

    def test_boundary_conditions_validate_physical_dimensions(self):
        fixed = BoundaryCondition("B1", "mount", "fixed")
        self.assertEqual(fixed.kind, "fixed")
        displacement = BoundaryCondition(
            "B2", "node-1", "displacement",
            (Quantity(0,"mm"), Quantity(0,"mm"), Quantity(1,"mm")),
        )
        self.assertAlmostEqual(displacement.components[2].to("m").value, 0.001)
        pressure = BoundaryCondition("B3", "panel-1", "pressure", (Quantity(20,"kPa"),))
        self.assertEqual(pressure.components[0].to("Pa").value, 20000)

    def test_rejects_incomplete_boundary_conditions(self):
        with self.assertRaisesRegex(ValueError, "requires three"):
            BoundaryCondition("B", "node", "displacement", (Quantity(0,"m"),))
        with self.assertRaisesRegex(ValueError, "incompatible"):
            BoundaryCondition("B", "panel", "pressure", (Quantity(20,"m"),))


if __name__ == "__main__":
    unittest.main()
