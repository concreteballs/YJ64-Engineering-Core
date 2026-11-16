"""Physics solver interfaces and reference implementations."""

from .aerodynamics import AerodynamicsSolver
from .calculix import CalculiXTrussSolver
from .hydrodynamics import HydrodynamicsSolver
from .sail import SailAerodynamicsSolver
from .sail_material import SailMaterialSolver
from .apparent_wind import ApparentWindSolver
from .hydrostatics import CatamaranHydrostaticsSolver
from .mass_budget import VesselMassBudgetSolver
from .rov_pressure_housing import ROVPressureHousingSolver
from .hydrostatic_panel_loads import HydrostaticPanelLoadSolver
from .hull_material import HullMaterialScreeningSolver
from .vessel_motion import VesselMotionKinematicsSolver
from .kernel import (
    BUILTIN_UNIT_PROFILES, EUROPEAN_METRIC_PROFILE, MARINE_HYBRID_PROFILE,
    METRIC_ENGINEERING_PROFILE, SI_PROFILE, UK_IMPERIAL_PROFILE, US_CUSTOMARY_PROFILE,
    DocumentUnitPolicy, NominalSizeDesignation, UnitDisplayPreferences, UnitSystemProfile,
    VoiceUnitCommand, convert_by_voice, parse_voice_unit_command,
    AppliedLoad, BoundaryCondition, CoordinateFrame, CoordinateFrameRegistry,
    RigidTransform, AxisAlignedBoundingBox, Cylinder, GeometryPoint,
    GeometryVector, LineSegment, Plane, Sphere, FORCE, MOMENT, PRESSURE,
    AirDensityResult, DEFAULT_UNIT_REGISTRY, MaterialLibrary,
    MaterialPropertyEvidence, MaterialRecord, Quantity, SeawaterDensityResult,
    UnitDefinition, UnitRegistry, dry_air_density_ideal_kg_m3,
    seawater_density_eos80_kg_m3,
)

__all__ = [
    "BUILTIN_UNIT_PROFILES", "EUROPEAN_METRIC_PROFILE", "MARINE_HYBRID_PROFILE",
    "METRIC_ENGINEERING_PROFILE", "SI_PROFILE", "UK_IMPERIAL_PROFILE", "US_CUSTOMARY_PROFILE",
    "DocumentUnitPolicy", "NominalSizeDesignation", "UnitDisplayPreferences", "UnitSystemProfile",
    "VoiceUnitCommand", "convert_by_voice", "parse_voice_unit_command",
    "AppliedLoad", "BoundaryCondition", "CoordinateFrame", "CoordinateFrameRegistry",
    "RigidTransform", "AxisAlignedBoundingBox", "Cylinder", "GeometryPoint",
    "GeometryVector", "LineSegment", "Plane", "Sphere", "FORCE", "MOMENT", "PRESSURE",
    "AerodynamicsSolver", "CalculiXTrussSolver", "HydrodynamicsSolver",
    "SailAerodynamicsSolver", "SailMaterialSolver", "ApparentWindSolver",
    "CatamaranHydrostaticsSolver", "VesselMassBudgetSolver",
    "HullMaterialScreeningSolver", "ROVPressureHousingSolver",
    "HydrostaticPanelLoadSolver", "VesselMotionKinematicsSolver",
    "AirDensityResult", "DEFAULT_UNIT_REGISTRY", "MaterialLibrary",
    "MaterialPropertyEvidence", "MaterialRecord", "Quantity",
    "SeawaterDensityResult", "UnitDefinition", "UnitRegistry",
    "dry_air_density_ideal_kg_m3", "seawater_density_eos80_kg_m3",
]
