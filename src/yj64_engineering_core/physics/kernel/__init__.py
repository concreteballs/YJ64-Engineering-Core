"""Shared physical-kernel primitives used by discipline-specific solver packs."""

from .environment import (
    AirDensityResult,
    SeawaterDensityResult,
    dry_air_density_ideal_kg_m3,
    seawater_density_eos80_kg_m3,
)
from .materials import MaterialLibrary, MaterialPropertyEvidence, MaterialRecord
from .quantities import (
    DEFAULT_UNIT_REGISTRY,
    Quantity,
    UnitDefinition,
    UnitRegistry,
)

__all__ = [
    "AirDensityResult", "DEFAULT_UNIT_REGISTRY", "MaterialLibrary",
    "MaterialPropertyEvidence", "MaterialRecord", "Quantity",
    "SeawaterDensityResult", "UnitDefinition", "UnitRegistry",
    "dry_air_density_ideal_kg_m3", "seawater_density_eos80_kg_m3",
]
