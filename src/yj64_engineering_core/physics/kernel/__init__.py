"""Shared physical-kernel primitives used by discipline-specific solver packs."""

from .environment import (
    AirDensityResult,
    SeawaterDensityResult,
    dry_air_density_ideal_kg_m3,
    seawater_density_eos80_kg_m3,
)
from .materials import MaterialLibrary, MaterialPropertyEvidence, MaterialRecord
from .coordinate_frames import CoordinateFrame, CoordinateFrameRegistry, RigidTransform
from .geometry import (
    AxisAlignedBoundingBox, Cylinder, GeometryPoint, GeometryVector,
    LineSegment, Plane, Sphere,
)
from .conditions import AppliedLoad, BoundaryCondition
from .quantities import (
    DEFAULT_UNIT_REGISTRY, FORCE, MOMENT, PRESSURE,
    Quantity,
    UnitDefinition,
    UnitRegistry,
)

__all__ = [
    "AppliedLoad", "BoundaryCondition", "CoordinateFrame", "CoordinateFrameRegistry",
    "RigidTransform", "AxisAlignedBoundingBox", "Cylinder", "GeometryPoint",
    "GeometryVector", "LineSegment", "Plane", "Sphere", "FORCE", "MOMENT", "PRESSURE",
    "AirDensityResult", "DEFAULT_UNIT_REGISTRY", "MaterialLibrary",
    "MaterialPropertyEvidence", "MaterialRecord", "Quantity",
    "SeawaterDensityResult", "UnitDefinition", "UnitRegistry",
    "dry_air_density_ideal_kg_m3", "seawater_density_eos80_kg_m3",
]
