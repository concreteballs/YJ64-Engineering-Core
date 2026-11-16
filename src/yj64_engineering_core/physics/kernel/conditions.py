"""Typed engineering loads and boundary conditions.

All spatial coordinates are metres and all values carry explicit registered
units. This module describes inputs; it does not apply loads to a mesh or solve
a structural/thermal/electrical boundary-value problem.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .geometry import GeometryPoint
from .quantities import Quantity, FORCE, MOMENT, PRESSURE, LENGTH, DIMENSIONLESS, TEMPERATURE

LoadKind = Literal["force", "moment"]
LoadDistribution = Literal["point", "uniform", "linear"]
BoundaryKind = Literal["fixed", "displacement", "rotation", "pressure", "temperature"]


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")


@dataclass(frozen=True, slots=True)
class AppliedLoad:
    load_id: str
    target_id: str
    kind: LoadKind
    components: tuple[Quantity, Quantity, Quantity]
    frame_id: str
    distribution: LoadDistribution = "point"
    application_point: GeometryPoint | None = None
    description: str = ""

    def __post_init__(self) -> None:
        for name in ("load_id", "target_id", "frame_id"):
            _identifier(getattr(self, name), name)
        if self.kind not in ("force", "moment"):
            raise ValueError("kind must be 'force' or 'moment'")
        if self.distribution not in ("point", "uniform", "linear"):
            raise ValueError("unsupported load distribution")
        if not isinstance(self.components, tuple) or len(self.components) != 3:
            raise ValueError("components must be a tuple of three quantities")
        expected = FORCE if self.kind == "force" else MOMENT
        for component in self.components:
            if not isinstance(component, Quantity):
                raise TypeError("load components must be Quantity values")
            if component.dimension != expected:
                raise ValueError(f"{self.kind} components must have dimension {expected}")
        if self.application_point is not None and self.application_point.frame_id != self.frame_id:
            raise ValueError("application point must use the load coordinate frame")


@dataclass(frozen=True, slots=True)
class BoundaryCondition:
    condition_id: str
    target_id: str
    kind: BoundaryKind
    components: tuple[Quantity, ...] = ()
    frame_id: str = "world"
    description: str = ""

    def __post_init__(self) -> None:
        for name in ("condition_id", "target_id", "frame_id"):
            _identifier(getattr(self, name), name)
        expected = {
            "fixed": None,
            "displacement": LENGTH,
            "rotation": DIMENSIONLESS,
            "pressure": PRESSURE,
            "temperature": TEMPERATURE,
        }
        if self.kind not in expected:
            raise ValueError("unsupported boundary-condition kind")
        if self.kind == "fixed":
            if self.components:
                raise ValueError("fixed boundary condition does not accept components")
            return
        if not self.components:
            raise ValueError(f"{self.kind} boundary condition requires components")
        if self.kind in ("displacement", "rotation") and len(self.components) != 3:
            raise ValueError(f"{self.kind} boundary condition requires three components")
        if self.kind in ("pressure", "temperature") and len(self.components) != 1:
            raise ValueError(f"{self.kind} boundary condition requires one component")
        for component in self.components:
            if not isinstance(component, Quantity):
                raise TypeError("boundary-condition components must be Quantity values")
            if component.dimension != expected[self.kind]:
                raise ValueError(f"{self.kind} component has incompatible physical dimension")
