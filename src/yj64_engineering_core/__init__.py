"""YJ64 Engineering Core public API."""
from .contracts import CONTRACT_VERSION, ArtifactReference, EngineeringRequest, EngineeringResponse, GeometrySpec, LoadCase, SolverProvenance
from .component_model import ComponentCalculationRecord, ComponentDependency, ComponentInterface, ComponentMassProperties, EngineeringComponent, EngineeringProjectGraph, EvidenceRecord, ManufacturingConstraint, stale_calculations, stale_component_dependencies
from .dispatcher import AxialMemberSolver, DispatchResult, EngineeringDispatcher
from .cad.adapters import FreeCADMacroBackend, OpenSCADSourceBackend, SVGDrawingBackend
from .cad.hull import HullStation, YachtHull
from .cad.hull_adapters import YachtHullCADBackend
from .cad.hull_edits import apply_hull_changes
from .cad.visual_reference import ImageAnnotation, VisualObservation, VisualReference, ingest_reference_image, visual_changes
from .models import AnalysisRequest, AnalysisResult, MaterialProperties, Point3D
from .pipeline import EngineeringPipeline, PipelineBranch, PipelineResult
from .physics.aerodynamics import AerodynamicsSolver
from .physics.calculix import CalculiXTrussSolver
from .physics.hydrodynamics import HydrodynamicsSolver
from .physics.sail import SailAerodynamicsSolver
from .physics.sail_material import SailMaterialSolver
from .physics.apparent_wind import ApparentWindSolver
from .physics.hydrostatics import CatamaranHydrostaticsSolver
from .physics.mass_budget import VesselMassBudgetSolver
from .physics.hull_material import HullMaterialScreeningSolver
from .physics.rov_pressure_housing import ROVPressureHousingSolver

__all__ = [
    "CONTRACT_VERSION", "AerodynamicsSolver", "AnalysisRequest", "AnalysisResult",
    "ComponentCalculationRecord", "ComponentDependency", "ComponentInterface", "ComponentMassProperties", "EngineeringComponent", "EngineeringProjectGraph",
    "EvidenceRecord", "ManufacturingConstraint", "stale_calculations", "stale_component_dependencies",
    "ArtifactReference", "AxialMemberSolver", "CalculiXTrussSolver", "DispatchResult",
    "EngineeringDispatcher", "EngineeringPipeline", "EngineeringRequest", "EngineeringResponse",
    "FreeCADMacroBackend", "GeometrySpec", "HullStation", "YachtHull", "YachtHullCADBackend",
    "HydrodynamicsSolver", "SailAerodynamicsSolver", "SailMaterialSolver", "ApparentWindSolver",
    "CatamaranHydrostaticsSolver", "VesselMassBudgetSolver", "HullMaterialScreeningSolver", "ROVPressureHousingSolver",
    "ImageAnnotation", "VisualObservation", "VisualReference", "apply_hull_changes",
    "ingest_reference_image", "visual_changes", "LoadCase", "MaterialProperties",
    "OpenSCADSourceBackend", "PipelineBranch", "PipelineResult", "Point3D",
    "SVGDrawingBackend", "SolverProvenance",
]
__version__ = "0.1.0"
