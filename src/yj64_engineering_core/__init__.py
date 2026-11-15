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

__all__ = [
    "CONTRACT_VERSION",
    "AnalysisRequest",
    "AnalysisResult",
    "ArtifactReference",
    "AxialMemberSolver",
    "DispatchResult",
    "EngineeringDispatcher",
    "EngineeringRequest",
    "EngineeringResponse",
    "FreeCADMacroBackend",
    "GeometrySpec",
    "LoadCase",
    "MaterialProperties",
    "OpenSCADSourceBackend",
    "Point3D",
    "SVGDrawingBackend",
    "SolverProvenance",
]

__version__ = "0.1.0"
