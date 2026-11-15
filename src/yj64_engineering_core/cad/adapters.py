"""Workspace-bound CAD adapters for the built-in source generators."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from .drawing2d import cylinder_orthographic_svg
from .freecad import build_cylinder_macro
from .openscad import cylinder_scad


def _safe_basename(request_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", request_id)
    return cleaned[:64] or "yj64_part"


class _WorkspaceBackend:
    name = "YJ64 CAD backend"
    version = "0.1.0"

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def supported_formats(self) -> tuple[str, ...]:
        return ()

    def _target(self, filename: str) -> Path:
        target = (self.workspace / filename).resolve()
        if target.parent != self.workspace:
            raise ValueError("Artifact path escaped the configured CAD workspace")
        return target

    @staticmethod
    def _cylinder_dimensions(specification: dict[str, Any]) -> tuple[float, float]:
        if specification.get("geometry_type") != "cylinder":
            raise ValueError("This CAD adapter currently supports cylinder geometry only")
        parameters = specification.get("parameters", {})
        radius_m = parameters.get("radius_m")
        if radius_m is None and "diameter_m" in parameters:
            radius_m = parameters["diameter_m"] / 2.0
        height_m = parameters.get("height_m")
        if radius_m is None or height_m is None:
            raise ValueError("Cylinder requires radius_m or diameter_m, and height_m")
        for name, value in (("radius_m", radius_m), ("height_m", height_m)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        return float(radius_m) * 1000.0, float(height_m) * 1000.0


class OpenSCADSourceBackend(_WorkspaceBackend):
    """Write editable OpenSCAD source; does not invoke the OpenSCAD executable."""

    name = "YJ64 OpenSCAD source generator"

    def supported_formats(self) -> tuple[str, ...]:
        return ("scad",)

    def generate(self, specification: dict) -> dict:
        radius_mm, height_mm = self._cylinder_dimensions(specification)
        source = cylinder_scad(radius_mm=radius_mm, height_mm=height_mm)
        path = self._target(f"{_safe_basename(specification['request_id'])}.scad")
        path.write_text(source, encoding="utf-8")
        return {
            "format": "application/x-openscad",
            "location": path.as_uri(),
            "warnings": [],
            "limitations": ["Source generated only; OpenSCAD was not executed or rendered."],
        }


class FreeCADMacroBackend(_WorkspaceBackend):
    """Write a FreeCAD macro; never executes FreeCAD automatically."""

    name = "YJ64 FreeCAD macro generator"

    def supported_formats(self) -> tuple[str, ...]:
        return ("FCMacro",)

    def generate(self, specification: dict) -> dict:
        radius_mm, height_mm = self._cylinder_dimensions(specification)
        basename = _safe_basename(specification["request_id"])
        macro = build_cylinder_macro(
            radius_mm=radius_mm,
            height_mm=height_mm,
            output_dir=self.workspace,
            basename=basename,
        )
        path = self._target(f"{basename}.FCMacro")
        path.write_text(macro, encoding="utf-8")
        return {
            "format": "text/x-freecad-macro",
            "location": path.as_uri(),
            "warnings": [],
            "limitations": [
                "Macro generated only; FreeCAD was not executed.",
                "Review the macro and export paths before running it.",
            ],
        }


class SVGDrawingBackend(_WorkspaceBackend):
    """Write a schematic orthographic SVG drawing for a cylinder."""

    name = "YJ64 SVG drawing generator"

    def supported_formats(self) -> tuple[str, ...]:
        return ("svg",)

    def generate(self, specification: dict) -> dict:
        radius_mm, height_mm = self._cylinder_dimensions(specification)
        drawing = cylinder_orthographic_svg(
            radius_mm=radius_mm, height_mm=height_mm
        )
        path = self._target(f"{_safe_basename(specification['request_id'])}.svg")
        path.write_text(drawing, encoding="utf-8")
        return {
            "format": "image/svg+xml",
            "location": path.as_uri(),
            "warnings": ["Schematic drawing; not a manufacturing drawing."],
            "limitations": [
                "No tolerances, GD&T, surface finish, or manufacturing notes are included."
            ],
        }
