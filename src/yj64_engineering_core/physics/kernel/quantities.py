"""Unit-aware physical quantities and a small extensible SI unit registry.

The registry intentionally contains explicit, named units rather than parsing
arbitrary unit expressions. This keeps conversions auditable and avoids
silently accepting ambiguous or misspelled units.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

# SI base-dimension order: mass, length, time, electric current,
# thermodynamic temperature, amount of substance, luminous intensity.
Dimension = tuple[int, int, int, int, int, int, int]
DIMENSIONLESS: Dimension = (0, 0, 0, 0, 0, 0, 0)
MASS: Dimension = (1, 0, 0, 0, 0, 0, 0)
LENGTH: Dimension = (0, 1, 0, 0, 0, 0, 0)
TIME: Dimension = (0, 0, 1, 0, 0, 0, 0)
CURRENT: Dimension = (0, 0, 0, 1, 0, 0, 0)
TEMPERATURE: Dimension = (0, 0, 0, 0, 1, 0, 0)
AMOUNT: Dimension = (0, 0, 0, 0, 0, 1, 0)
LUMINOUS_INTENSITY: Dimension = (0, 0, 0, 0, 0, 0, 1)
FORCE: Dimension = (1, 1, -2, 0, 0, 0, 0)
MOMENT: Dimension = (1, 2, -2, 0, 0, 0, 0)
PRESSURE: Dimension = (1, -1, -2, 0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """Conversion from a named unit to SI base units: SI = value*scale+offset."""

    symbol: str
    dimension: Dimension
    scale_to_si: float = 1.0
    offset_to_si: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol.strip() != self.symbol:
            raise ValueError("unit symbol must be non-empty and have no surrounding whitespace")
        if len(self.dimension) != 7 or any(not isinstance(x, int) for x in self.dimension):
            raise ValueError("dimension must contain seven integer SI exponents")
        if not math.isfinite(self.scale_to_si) or self.scale_to_si <= 0:
            raise ValueError("scale_to_si must be finite and greater than zero")
        if not math.isfinite(self.offset_to_si):
            raise ValueError("offset_to_si must be finite")


class UnitRegistry:
    """Explicit, extensible registry of named units."""

    def __init__(self, units: Iterable[UnitDefinition] = ()) -> None:
        self._units: dict[str, UnitDefinition] = {}
        for unit in units:
            self.register(unit)

    def register(self, unit: UnitDefinition) -> None:
        if not isinstance(unit, UnitDefinition):
            raise TypeError("unit must be a UnitDefinition")
        if unit.symbol in self._units:
            raise ValueError(f"unit '{unit.symbol}' is already registered")
        self._units[unit.symbol] = unit

    def get(self, symbol: str) -> UnitDefinition:
        try:
            return self._units[symbol]
        except KeyError as exc:
            raise ValueError(f"unknown unit '{symbol}'") from exc

    def symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._units))


def _build_default_registry() -> UnitRegistry:
    units = [
        UnitDefinition("1", DIMENSIONLESS),
        UnitDefinition("%", DIMENSIONLESS, 0.01),
        UnitDefinition("kg", MASS),
        UnitDefinition("g", MASS, 1e-3),
        UnitDefinition("t", MASS, 1e3),
        UnitDefinition("m", LENGTH),
        UnitDefinition("mm", LENGTH, 1e-3),
        UnitDefinition("cm", LENGTH, 1e-2),
        UnitDefinition("km", LENGTH, 1e3),
        UnitDefinition("m2", (0, 2, 0, 0, 0, 0, 0)),
        UnitDefinition("mm2", (0, 2, 0, 0, 0, 0, 0), 1e-6),
        UnitDefinition("m3", (0, 3, 0, 0, 0, 0, 0)),
        UnitDefinition("L", (0, 3, 0, 0, 0, 0, 0), 1e-3),
        UnitDefinition("s", TIME),
        UnitDefinition("min", TIME, 60.0),
        UnitDefinition("h", TIME, 3600.0),
        UnitDefinition("A", CURRENT),
        UnitDefinition("K", TEMPERATURE),
        UnitDefinition("degC", TEMPERATURE, 1.0, 273.15),
        UnitDefinition("mol", AMOUNT),
        UnitDefinition("cd", LUMINOUS_INTENSITY),
        UnitDefinition("rad", DIMENSIONLESS),
        UnitDefinition("deg", DIMENSIONLESS, math.pi / 180.0),
        UnitDefinition("Hz", (0, 0, -1, 0, 0, 0, 0)),
        UnitDefinition("N", FORCE),
        UnitDefinition("N*m", MOMENT),
        UnitDefinition("kN", (1, 1, -2, 0, 0, 0, 0), 1e3),
        UnitDefinition("Pa", PRESSURE),
        UnitDefinition("kPa", (1, -1, -2, 0, 0, 0, 0), 1e3),
        UnitDefinition("MPa", (1, -1, -2, 0, 0, 0, 0), 1e6),
        UnitDefinition("bar", (1, -1, -2, 0, 0, 0, 0), 1e5),
        UnitDefinition("J", (1, 2, -2, 0, 0, 0, 0)),
        UnitDefinition("kJ", (1, 2, -2, 0, 0, 0, 0), 1e3),
        UnitDefinition("W", (1, 2, -3, 0, 0, 0, 0)),
        UnitDefinition("kW", (1, 2, -3, 0, 0, 0, 0), 1e3),
        UnitDefinition("C", (0, 0, 1, 1, 0, 0, 0)),
        UnitDefinition("V", (1, 2, -3, -1, 0, 0, 0)),
        UnitDefinition("ohm", (1, 2, -3, -2, 0, 0, 0)),
        UnitDefinition("kg/m3", (1, -3, 0, 0, 0, 0, 0)),
        UnitDefinition("m/s", (0, 1, -1, 0, 0, 0, 0)),
        UnitDefinition("m/s2", (0, 1, -2, 0, 0, 0, 0)),
    ]
    return UnitRegistry(units)


DEFAULT_UNIT_REGISTRY = _build_default_registry()


@dataclass(frozen=True, slots=True)
class Quantity:
    """A finite numeric value associated with a registered physical unit."""

    value: float
    unit: str
    registry: UnitRegistry = field(default=DEFAULT_UNIT_REGISTRY, compare=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("quantity value must be a real number")
        if not math.isfinite(float(self.value)):
            raise ValueError("quantity value must be finite")
        self.registry.get(self.unit)

    @property
    def dimension(self) -> Dimension:
        return self.registry.get(self.unit).dimension

    @property
    def si_value(self) -> float:
        definition = self.registry.get(self.unit)
        return float(self.value) * definition.scale_to_si + definition.offset_to_si

    def to(self, target_unit: str) -> "Quantity":
        source = self.registry.get(self.unit)
        target = self.registry.get(target_unit)
        if source.dimension != target.dimension:
            raise ValueError(
                f"incompatible dimensions: '{self.unit}' cannot be converted to '{target_unit}'"
            )
        converted = (self.si_value - target.offset_to_si) / target.scale_to_si
        return Quantity(converted, target_unit, self.registry)

    def to_dict(self) -> dict[str, object]:
        return {
            "value": float(self.value),
            "unit": self.unit,
            "dimension": list(self.dimension),
            "si_value": self.si_value,
        }
