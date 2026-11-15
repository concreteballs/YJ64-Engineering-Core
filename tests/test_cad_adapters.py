import tempfile
import unittest
from pathlib import Path

from yj64_engineering_core.cad.adapters import (
    FreeCADMacroBackend,
    OpenSCADSourceBackend,
    SVGDrawingBackend,
)
from yj64_engineering_core.contracts import EngineeringRequest, GeometrySpec
from yj64_engineering_core.dispatcher import EngineeringDispatcher


class CADAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.request = EngineeringRequest(
            request_id="cad-cylinder-001",
            title="Cylinder",
            objective="Generate cylinder CAD artifacts",
            geometry=GeometrySpec(
                "cylinder",
                {"diameter_m": 0.05, "height_m": 0.12},
            ),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_openscad_backend_writes_source(self):
        backend = OpenSCADSourceBackend(self.workspace)
        result = backend.generate({
            "request_id": self.request.request_id,
            "geometry_type": "cylinder",
            "parameters": self.request.geometry.parameters,
        })
        path = self.workspace / "cad-cylinder-001.scad"
        self.assertTrue(path.is_file())
        self.assertIn("cylinder(", path.read_text(encoding="utf-8"))
        self.assertEqual(result["format"], "application/x-openscad")

    def test_freecad_backend_writes_macro_without_running_it(self):
        backend = FreeCADMacroBackend(self.workspace)
        result = backend.generate({
            "request_id": self.request.request_id,
            "geometry_type": "cylinder",
            "parameters": self.request.geometry.parameters,
        })
        path = self.workspace / "cad-cylinder-001.FCMacro"
        self.assertTrue(path.is_file())
        self.assertIn("Part::Cylinder", path.read_text(encoding="utf-8"))
        self.assertIn("not executed", " ".join(result["limitations"]).lower())

    def test_svg_backend_writes_schematic_drawing(self):
        backend = SVGDrawingBackend(self.workspace)
        result = backend.generate({
            "request_id": self.request.request_id,
            "geometry_type": "cylinder",
            "parameters": self.request.geometry.parameters,
        })
        path = self.workspace / "cad-cylinder-001.svg"
        self.assertTrue(path.is_file())
        self.assertIn("<svg", path.read_text(encoding="utf-8"))
        self.assertEqual(result["format"], "image/svg+xml")

    def test_dispatcher_returns_real_cad_artifact_reference(self):
        dispatcher = EngineeringDispatcher()
        dispatcher.register_cad_backend(
            "openscad", OpenSCADSourceBackend(self.workspace)
        )
        request = EngineeringRequest(
            request_id="through-dispatcher",
            title="Cylinder",
            objective="Generate source",
            geometry=GeometrySpec("cylinder", {"radius_m": 0.02, "height_m": 0.1}),
            operating_conditions={"cad_backend": "openscad"},
        )
        result = dispatcher.dispatch(request, "cad.generate")
        self.assertEqual(result.response.values["artifact_count"], 1)
        self.assertTrue(result.response.artifacts[0].uri.endswith("through-dispatcher.scad"))

    def test_rejects_boolean_dimension(self):
        backend = OpenSCADSourceBackend(self.workspace)
        with self.assertRaisesRegex(TypeError, "radius_m must be numeric"):
            backend.generate({
                "request_id": "bad-dimension",
                "geometry_type": "cylinder",
                "parameters": {"radius_m": True, "height_m": 0.1},
            })

    def test_rejects_non_finite_dimension(self):
        backend = OpenSCADSourceBackend(self.workspace)
        with self.assertRaisesRegex(ValueError, "radius_m must be finite"):
            backend.generate({
                "request_id": "bad-dimension",
                "geometry_type": "cylinder",
                "parameters": {"radius_m": float("inf"), "height_m": 0.1},
            })

    def test_rejects_unsupported_geometry(self):
        backend = OpenSCADSourceBackend(self.workspace)
        with self.assertRaisesRegex(ValueError, "cylinder geometry only"):
            backend.generate({
                "request_id": "wrong-shape",
                "geometry_type": "gear",
                "parameters": {},
            })


if __name__ == "__main__":
    unittest.main()
