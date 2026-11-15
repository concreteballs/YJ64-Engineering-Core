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
    "GeometrySpec",
    "LoadCase",
    "MaterialProperties",
    "Point3D",
    "SolverProvenance",
]

__version__ = "0.1.0"
