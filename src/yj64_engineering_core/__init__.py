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
