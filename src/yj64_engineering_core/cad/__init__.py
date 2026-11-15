"""CAD backends and geometry exporters."""

from .adapters import FreeCADMacroBackend, OpenSCADSourceBackend, SVGDrawingBackend
from .hull import HullStation, YachtHull, yacht_hull_openscad, yacht_hull_technical_svg
from .hull_adapters import YachtHullCADBackend
from .hull_edits import apply_hull_changes
from .visual_reference import ImageAnnotation, VisualObservation, VisualReference, ingest_reference_image, visual_changes

__all__ = [
    "FreeCADMacroBackend",
    "OpenSCADSourceBackend",
    "SVGDrawingBackend",
    "HullStation",
    "YachtHull",
    "YachtHullCADBackend",
    "ImageAnnotation",
    "VisualObservation",
    "VisualReference",
    "apply_hull_changes",
    "ingest_reference_image",
    "visual_changes",
    "yacht_hull_openscad",
    "yacht_hull_technical_svg",
]
