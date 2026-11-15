"""Typed data contracts. All numeric engineering values use SI units."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Point3D:
    """A point in metres in a right-handed Cartesian coordinate system."""

    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")


@dataclass(frozen=True)
class MaterialProperties:
    """Minimal material data. Values are SI units."""

    name: str
    youngs_modulus_pa: float
    allowable_stress_pa: float
    density_kg_m3: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Material name cannot be empty")
        if self.youngs_modulus_pa <= 0:
            raise ValueError("Young's modulus must be positive")
        if self.allowable_stress_pa <= 0:
            raise ValueError("Allowable stress must be positive")
        if self.density_kg_m3 is not None and self.density_kg_m3 <= 0:
            raise ValueError("Density must be positive when supplied")


@dataclass(frozen=True)
class AnalysisRequest:
    """Input for a named engineering analysis."""

    analysis_type: str
    parameters: dict[str, Any]
    units: str = "SI"
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.analysis_type.strip():
            raise ValueError("analysis_type cannot be empty")
        if self.units != "SI":
            raise ValueError("Version 0.1 accepts SI units only")
        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a dictionary")


@dataclass
class AnalysisResult:
    """Solver output with explicit method and limitations."""

    analysis_type: str
    status: str
    values: dict[str, Any]
    units: dict[str, str]
    method: str
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    solver_name: str = "unknown"
    solver_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
