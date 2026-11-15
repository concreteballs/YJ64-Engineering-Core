import tempfile
import unittest
from pathlib import Path

from yj64_engineering_core.cad.drawing2d import cylinder_orthographic_svg, write_cylinder_svg
from yj64_engineering_core.cad.freecad import build_cylinder_macro


class FreeCADMacroTests(unittest.TestCase):
    def test_macro_contains_parametric_part_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = build_cylinder_macro(radius_mm=12.5, height_mm=40, output_dir=tmp)
        self.assertIn('doc.addObject("Part::Cylinder", "Cylinder")', source)
        self.assertIn("cylinder.Radius = 12.5", source)
        self.assertIn(".step", source)
        self.assertIn(".stl", source)
        self.assertIn(".FCStd", source)

    def test_rejects_unsafe_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_cylinder_macro(radius_mm=2, height_mm=5, output_dir=tmp, basename="../bad")


class DrawingTests(unittest.TestCase):
    def test_svg_contains_views_and_dimensions(self):
        svg = cylinder_orthographic_svg(radius_mm=10, height_mm=30)
        self.assertIn("TOP VIEW", svg)
        self.assertIn("SIDE VIEW", svg)
        self.assertIn("D = 20 mm", svg)
        self.assertIn("L = 30 mm", svg)

    def test_svg_can_be_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_cylinder_svg(radius_mm=10, height_mm=30, output_path=Path(tmp) / "part.svg")
            self.assertTrue(path.is_file())
            self.assertTrue(path.read_text(encoding="utf-8").startswith("<svg"))


if __name__ == "__main__":
    unittest.main()
