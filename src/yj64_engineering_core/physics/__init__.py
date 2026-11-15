"""Physics solver interfaces and reference implementations."""

from .aerodynamics import AerodynamicsSolver
from .calculix import CalculiXTrussSolver
from .hydrodynamics import HydrodynamicsSolver
from .sail import SailAerodynamicsSolver
from .sail_material import SailMaterialSolver
from .apparent_wind import ApparentWindSolver
from .hydrostatics import CatamaranHydrostaticsSolver
from .mass_budget import VesselMassBudgetSolver

__all__ = [
    "AerodynamicsSolver",
    "CalculiXTrussSolver",
    "HydrodynamicsSolver",
    "SailAerodynamicsSolver",
    "SailMaterialSolver",
    "ApparentWindSolver",
    "CatamaranHydrostaticsSolver",
    "VesselMassBudgetSolver",
]
