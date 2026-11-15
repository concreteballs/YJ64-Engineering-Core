"""Physics solver interfaces and reference implementations."""

from .aerodynamics import AerodynamicsSolver
from .calculix import CalculiXTrussSolver
from .hydrodynamics import HydrodynamicsSolver
from .sail import SailAerodynamicsSolver
from .sail_material import SailMaterialSolver
from .apparent_wind import ApparentWindSolver

__all__ = [
    "AerodynamicsSolver",
    "CalculiXTrussSolver",
    "HydrodynamicsSolver",
    "SailAerodynamicsSolver",
    "SailMaterialSolver",
    "ApparentWindSolver",
]
