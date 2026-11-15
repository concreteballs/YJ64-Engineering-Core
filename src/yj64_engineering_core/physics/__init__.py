"""Physics solver interfaces and reference implementations."""

from .aerodynamics import AerodynamicsSolver
from .calculix import CalculiXTrussSolver
from .hydrodynamics import HydrodynamicsSolver

__all__ = [
    "AerodynamicsSolver",
    "CalculiXTrussSolver",
    "HydrodynamicsSolver",
]
