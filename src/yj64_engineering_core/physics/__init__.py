"""Physics solver interfaces and reference implementations."""

from .aerodynamics import AerodynamicsSolver
from .calculix import CalculiXTrussSolver
from .hydrodynamics import HydrodynamicsSolver
from .sail import SailAerodynamicsSolver

__all__ = [
    "AerodynamicsSolver",
    "CalculiXTrussSolver",
    "HydrodynamicsSolver",
    "SailAerodynamicsSolver",
]
