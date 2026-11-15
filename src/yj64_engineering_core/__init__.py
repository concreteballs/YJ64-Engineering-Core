"""YJ64 Engineering Core public API."""

from .contracts import (
    CONTRACT_VERSION,
    ArtifactReference,
    EngineeringRequest,
    EngineeringResponse,
    GeometrySpec,
    LoadCase,
    SolverProvenance,
)
from .dispatcher import AxialMemberSolver, DispatchResult, EngineeringDispatcher
from .cad.adapters import FreeCADMacroBackend, OpenSCADSourceBackend, SVGDrawingBackend
from .cad.hull import HullStation, YachtHull
from .cad.hull_adapters import YachtHullCADBackend
from .cad.hull_edits import apply_hull_changes
from .cad.visual_reference import ImageAnnotation, VisualObservation, VisualReference, ingest_reference_image, visual_changes
from .models import (
    AnalysisRequest,
    AnalysisResult,
    MaterialProperties,
    Point3D,
)
from .pipeline import EngineeringPipeline, PipelineBranch, PipelineResult
from .physics.calculix import CalculiXTrussSolver

__all__ = [
    "CONTRACT_VERSION",
    "AnalysisRequest",
    "AnalysisResult",
    "ArtifactReference",
    "AxialMemberSolver",
    "CalculiXTrussSolver",
    "DispatchResult",
    "EngineeringDispatcher",
    "EngineeringPipeline",
    "EngineeringRequest",
    "EngineeringResponse",
    "FreeCADMacroBackend",
    "GeometrySpec",
    "HullStation",
    "YachtHull",
    "YachtHullCADBackend",
    "ImageAnnotation",
    "VisualObservation",
    "VisualReference",
    "apply_hull_changes",
    "ingest_reference_image",
    "visual_changes",
    "LoadCase",
    "MaterialProperties",
    "OpenSCADSourceBackend",
    "PipelineBranch",
    "PipelineResult",
    "Point3D",
    "SVGDrawingBackend",
    "SolverProvenance",
]

__version__ = "0.1.0"
