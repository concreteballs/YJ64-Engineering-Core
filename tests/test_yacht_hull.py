import math
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from yj64_engineering_core.cad.hull import (
    HullStation, YachtHull, hull_triangles, yacht_hull_openscad,
    yacht_hull_technical_svg,
)
from yj64_engineering_core.cad.hull_adapters import YachtHullCADBackend
from yj64_engineering_core.cad.hull_edits import apply_hull_changes
from yj64_engineering_core.cad.visual_reference import (
    ImageAnnotation, VisualObservation, ingest_reference_image, visual_changes,
)
from yj64_engineering_core.contracts import EngineeringRequest, GeometrySpec
from yj64_engineering_core.dispatcher import EngineeringDispatcher
from yj64_engineering_core.pipeline import EngineeringPipeline


def sample_hull():
    return YachtHull(
        name="Test mono-hull",
        stations=(
            HullStation(0.0, 0.025, -0.35, -0.10, 0.45),
            HullStation(1.0, 0.55, -0.55, -0.22, 0.65),
            HullStation(3.0, 0.90, -0.62, -0.24, 0.72),
            HullStation(5.0, 0.70, -0.50, -0.18, 0.68),
            HullStation(6.0, 0.025, -0.30, -0.08, 0.40),
        ),
    )


class YachtHullGeometryTests(unittest.TestCase):
    def test_validates_station_order_and_section_geometry(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            YachtHull("bad", (
                HullStation(0, .1, -.3, -.2, .4),
                HullStation(1, .2, -.3, -.2, .4),
                HullStation(1, .3, -.3, -.2, .4),
            ))
        with self.assertRaisesRegex(ValueError, "keel < chine < deck"):
            HullStation(0, .1, -.2, .3, .1)

    def test_round_trips_parametric_hull(self):
        hull = sample_hull()
        restored = YachtHull.from_parameters(hull.to_parameters())
        self.assertEqual(restored, hull)
        self.assertAlmostEqual(hull.length_m, 6.0)
        self.assertAlmostEqual(hull.maximum_beam_m, 1.8)

    def test_generates_three_dimensional_mesh_source(self):
        hull = sample_hull()
        source = yacht_hull_openscad(hull)
        self.assertIn("polyhedron(", source)
        self.assertIn("points = [", source)
        self.assertIn("faces = [", source)
        self.assertEqual(len(hull_triangles(hull)), 6 + 5 * 2 * (len(hull.stations)-1))

    def test_generates_three_view_technical_drawing(self):
        drawing = yacht_hull_technical_svg(sample_hull())
        self.assertIn("PLAN VIEW", drawing)
        self.assertIn("PROFILE VIEW", drawing)
        self.assertIn("TRANSVERSE SECTIONS", drawing)
        self.assertIn("Bmax = 1.800 m", drawing)
        self.assertIn("<svg", drawing)


class YachtHullEditTests(unittest.TestCase):
    def test_applies_wording_ready_structured_change_and_returns_diff(self):
        hull = sample_hull()
        updated, diff = apply_hull_changes(hull, [
            {"operation": "set_station", "station_index": 2,
             "field": "half_beam_m", "value": 1.0},
            {"operation": "rename", "name": "Wider test hull"},
        ])
        self.assertEqual(updated.name, "Wider test hull")
        self.assertAlmostEqual(updated.stations[2].half_beam_m, 1.0)
        self.assertTrue(diff["changed"])
        self.assertAlmostEqual(diff["before"]["stations"][2]["half_beam_m"], .9)

    def test_scales_beam_without_changing_length(self):
        hull = sample_hull()
        updated, _ = apply_hull_changes(hull, [{"operation": "scale_beam", "factor": 1.1}])
        self.assertAlmostEqual(updated.length_m, hull.length_m)
        self.assertAlmostEqual(updated.maximum_beam_m, hull.maximum_beam_m * 1.1)

    def test_rejects_arbitrary_code_or_unknown_operations(self):
        with self.assertRaisesRegex(ValueError, "Unsupported hull change"):
            apply_hull_changes(sample_hull(), [{"operation": "run_python", "code": "pass"}])


class VisualReferenceTests(unittest.TestCase):
    def test_ingests_png_and_keeps_annotation_coordinates_and_hash(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "markup.png"
            # Minimal PNG header with a valid IHDR width/height.
            header = (
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", 13) + b"IHDR"
                + struct.pack(">IIBBBBB", 320, 200, 8, 2, 0, 0, 0)
                + struct.pack(">I", 0)
            )
            path.write_bytes(header)
            annotation = ImageAnnotation(
                kind="arrow", points=((.45, .3), (.7, .4)),
                label="Widen midship", target_station_index=2,
                target_field="half_beam_m", target_value=1.05,
            )
            observation = VisualObservation(
                feature="midship sheer",
                description="The marked sheer line appears higher than the current model.",
                confidence=0.93,
                bbox=(0.35, 0.2, 0.25, 0.3),
                station_index=2,
                suggested_parameter="deck_z_m",
            )
            reference = ingest_reference_image(
                path, (annotation,), observations=(observation,)
            )
            self.assertEqual(reference.width_px, 320)
            self.assertEqual(reference.height_px, 200)
            self.assertEqual(len(reference.sha256), 64)
            self.assertEqual(reference.media_type, "image/png")
            self.assertEqual(visual_changes(reference)[0]["value"], 1.05)
            self.assertEqual(reference.observations[0].confidence, 0.93)
            updated, _ = apply_hull_changes(sample_hull(), visual_changes(reference))
            self.assertAlmostEqual(updated.stations[2].half_beam_m, 1.05)

    def test_rejects_out_of_bounds_annotation(self):
        with self.assertRaisesRegex(ValueError, "within 0..1"):
            ImageAnnotation(kind="point", points=((1.2, .5),))


class YachtHullCADTests(unittest.TestCase):
    def test_generates_svg_scad_and_freecad_macro_and_dispatches_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tempdir:
            backend = YachtHullCADBackend(tempdir)
            dispatcher = EngineeringDispatcher()
            dispatcher.register_cad_backend("yacht_hull", backend)
            request = EngineeringRequest(
                request_id="hull-design-001",
                title="Preliminary yacht hull",
                objective="Generate editable 2D and 3D hull artifacts",
                geometry=GeometrySpec("yacht_hull", sample_hull().to_parameters()),
                operating_conditions={"cad_backend": "yacht_hull"},
            )
            result = dispatcher.dispatch(request, "cad.generate")
            self.assertEqual(result.response.values["artifact_count"], 3)
            self.assertEqual(len(result.response.artifacts), 3)
            self.assertTrue((Path(tempdir) / "hull-design-001.svg").is_file())
            self.assertTrue((Path(tempdir) / "hull-design-001.scad").is_file())
            self.assertTrue((Path(tempdir) / "hull-design-001.FCMacro").is_file())
            self.assertIn("Part.makeLoft", (Path(tempdir) / "hull-design-001.FCMacro").read_text())


    def test_edited_hull_regenerates_both_2d_and_3d_artifacts(self):
        with tempfile.TemporaryDirectory() as tempdir:
            original = sample_hull()
            revised, change_record = apply_hull_changes(original, [
                {"operation": "set_station", "station_index": 2,
                 "field": "half_beam_m", "value": 1.05}
            ])
            backend = YachtHullCADBackend(tempdir)
            before = backend.generate({
                "request_id": "hull-revision-01",
                "geometry_type": "yacht_hull",
                "parameters": original.to_parameters(),
            })
            after = backend.generate({
                "request_id": "hull-revision-02",
                "geometry_type": "yacht_hull",
                "parameters": revised.to_parameters(),
            })
            self.assertTrue(change_record["changed"])
            self.assertEqual(len(before["artifacts"]), 3)
            self.assertEqual(len(after["artifacts"]), 3)
            self.assertNotEqual(
                (Path(tempdir) / "hull-revision-01.scad").read_text(),
                (Path(tempdir) / "hull-revision-02.scad").read_text(),
            )
            self.assertNotEqual(
                (Path(tempdir) / "hull-revision-01.svg").read_text(),
                (Path(tempdir) / "hull-revision-02.svg").read_text(),
            )

    def test_pipeline_supports_cad_only_design_iteration(self):
        with tempfile.TemporaryDirectory() as tempdir:
            dispatcher = EngineeringDispatcher()
            dispatcher.register_cad_backend("hull", YachtHullCADBackend(tempdir))
            request = EngineeringRequest(
                request_id="hull-cad-only",
                title="Hull sketch",
                objective="Create hull drawing before structural analysis",
                geometry=GeometrySpec("yacht_hull", sample_hull().to_parameters()),
                operating_conditions={"cad_backend": "hull"},
            )
            result = EngineeringPipeline(dispatcher).run(request)
            self.assertEqual(result.status, "completed")
            self.assertEqual(list(result.branches), ["cad"])
            self.assertEqual(result.branches["cad"].result.response.values["artifact_count"], 3)


@unittest.skipUnless(shutil.which("openscad"), "OpenSCAD executable is not installed")
class RealOpenSCADHullTests(unittest.TestCase):
    def test_real_openscad_renders_hull_to_stl(self):
        with tempfile.TemporaryDirectory() as tempdir:
            backend = YachtHullCADBackend(
                tempdir, openscad_executable=shutil.which("openscad"),
                render_stl=True, timeout_seconds=120,
            )
            result = backend.generate({
                "request_id": "real-hull-render",
                "geometry_type": "yacht_hull",
                "parameters": sample_hull().to_parameters(),
            })
            stl = Path(tempdir) / "real-hull-render.stl"
            self.assertTrue(stl.is_file())
            self.assertGreater(stl.stat().st_size, 84)
            self.assertEqual(len(result["artifacts"]), 4)
            self.assertEqual(result["artifacts"][-1]["format"], "model/stl")


if __name__ == "__main__":
    unittest.main()
