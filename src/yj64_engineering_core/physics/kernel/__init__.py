"""Shared physical-kernel primitives used by discipline-specific solver packs.

The kernel owns reusable, evidence-aware material and environment data. It does
not contain application-specific design rules or solver assumptions.
"""

from .environment import (
    AirDensityResult,
    SeawaterDensityResult,
    dry_air_density_ideal_kg_m3,
    seawater_density_eos80_kg_m3,
)
from .materials import MaterialLibrary, MaterialPropertyEvidence, MaterialRecord

__all__ = [
    "AirDensityResult", "MaterialLibrary", "MaterialPropertyEvidence",
    "MaterialRecord", "SeawaterDensityResult",
    "dry_air_density_ideal_kg_m3", "seawater_density_eos80_kg_m3",
]
