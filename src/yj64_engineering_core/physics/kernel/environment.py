"""Reusable environmental-property models with explicit validity limits.

Implemented models:
- dry-air density from the ideal-gas equation;
- seawater density at atmospheric pressure using UNESCO 1983 EOS-80.

These are property models, not complete atmosphere/ocean state solvers. Pressure
corrections for seawater, humidity effects in air, viscosity, conductivity,
sound speed and depth-dependent ocean profiles are intentionally separate work.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


DRY_AIR_SPECIFIC_GAS_CONSTANT_J_KG_K = 287.05287


def _finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True)
class AirDensityResult:
    density_kg_m3: float
    temperature_k: float
    absolute_pressure_pa: float
    model: str = "ideal_dry_air"
    assumptions: tuple[str, ...] = (
        "Air is treated as dry.",
        "Ideal-gas behaviour is assumed.",
    )
    validity: str = "Screening model; supplied temperature and pressure define the state."


@dataclass(frozen=True)
class SeawaterDensityResult:
    density_kg_m3: float
    temperature_c: float
    salinity_psu: float
    pressure_pa: float = 101325.0
    model: str = "UNESCO_1983_EOS80_atmospheric_pressure"
    assumptions: tuple[str, ...] = (
        "Atmospheric-pressure density equation is used.",
        "Pressure-compressibility correction is not included.",
        "Practical salinity is supplied in PSU.",
    )
    validity: str = "Temperature 0..40 degC; salinity 0..42 PSU; atmospheric pressure."


def dry_air_density_ideal_kg_m3(
    temperature_k: float,
    absolute_pressure_pa: float,
) -> AirDensityResult:
    """Calculate dry-air density using rho = p / (R_specific * T).

    Validated input envelope for this implementation is 180..330 K and
    30..120 kPa. The ideal-gas approximation is intended for engineering
    screening in ordinary atmospheric conditions, not high-pressure gas work.
    """
    _finite(temperature_k, "temperature_k")
    _finite(absolute_pressure_pa, "absolute_pressure_pa")
    if not 180.0 <= temperature_k <= 330.0:
        raise ValueError("temperature_k must be within the model range 180..330 K")
    if not 30000.0 <= absolute_pressure_pa <= 120000.0:
        raise ValueError("absolute_pressure_pa must be within the model range 30000..120000 Pa")
    density = absolute_pressure_pa / (
        DRY_AIR_SPECIFIC_GAS_CONSTANT_J_KG_K * temperature_k
    )
    return AirDensityResult(
        density_kg_m3=density,
        temperature_k=temperature_k,
        absolute_pressure_pa=absolute_pressure_pa,
    )


def seawater_density_eos80_kg_m3(
    temperature_c: float,
    salinity_psu: float,
) -> SeawaterDensityResult:
    """Calculate seawater density at atmospheric pressure using EOS-80.

    This is the UNESCO 1983 atmospheric-pressure polynomial. It is bounded to
    0..40 degC and 0..42 PSU. It does not apply the high-pressure secant-bulk-
    modulus correction; use a pressure-aware equation of state for deep water.
    """
    _finite(temperature_c, "temperature_c")
    _finite(salinity_psu, "salinity_psu")
    if not 0.0 <= temperature_c <= 40.0:
        raise ValueError("temperature_c must be within the EOS-80 range 0..40 degC")
    if not 0.0 <= salinity_psu <= 42.0:
        raise ValueError("salinity_psu must be within the EOS-80 range 0..42 PSU")

    t = temperature_c
    s = salinity_psu
    rho_water = (
        999.842594
        + 6.793952e-2 * t
        - 9.095290e-3 * t**2
        + 1.001685e-4 * t**3
        - 1.120083e-6 * t**4
        + 6.536332e-9 * t**5
    )
    a = (
        0.824493
        - 4.0899e-3 * t
        + 7.6438e-5 * t**2
        - 8.2467e-7 * t**3
        + 5.3875e-9 * t**4
    )
    b = -5.72466e-3 + 1.0227e-4 * t - 1.6546e-6 * t**2
    density = rho_water + a * s + b * s**1.5 + 4.8314e-4 * s**2
    return SeawaterDensityResult(
        density_kg_m3=density,
        temperature_c=temperature_c,
        salinity_psu=salinity_psu,
    )


def result_to_dict(result: AirDensityResult | SeawaterDensityResult) -> dict:
    """Serialize a typed environment result to a JSON-friendly dictionary."""
    return asdict(result)
