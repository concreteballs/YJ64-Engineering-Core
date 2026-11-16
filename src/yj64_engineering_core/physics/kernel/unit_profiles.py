"""Display-unit profiles, per-field overrides and voice-command intent parsing.

These helpers affect presentation/conversion only; canonical project values remain
unit-aware quantities and are never rewritten by a display-profile change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping

from .quantities import (
    DEFAULT_UNIT_REGISTRY, LENGTH, MASS, TIME, TEMPERATURE, FORCE, PRESSURE,
    Quantity, UnitRegistry,
)


class DocumentUnitPolicy(str, Enum):
    """How unit preferences are applied when importing/translating a document."""

    ASK = "ask"
    PRESERVE_SOURCE = "preserve_source"
    USE_PROFILE = "use_profile"


@dataclass(frozen=True, slots=True)
class UnitSystemProfile:
    profile_id: str
    label: str
    defaults: Mapping[tuple[int, ...], str]

    def __post_init__(self) -> None:
        if not self.profile_id.strip() or not self.label.strip():
            raise ValueError("profile_id and label must be non-empty")
        for dimension, symbol in self.defaults.items():
            if len(dimension) != 7:
                raise ValueError("profile dimensions must contain seven SI exponents")
            unit = DEFAULT_UNIT_REGISTRY.get(symbol)
            if tuple(dimension) != unit.dimension:
                raise ValueError(f"default unit '{symbol}' has the wrong dimension")


@dataclass(frozen=True, slots=True)
class UnitDisplayPreferences:
    """Profile defaults with explicit field-level engineering exceptions."""

    profile: UnitSystemProfile
    field_overrides: Mapping[str, str] = field(default_factory=dict)
    registry: UnitRegistry = field(default=DEFAULT_UNIT_REGISTRY, compare=False, repr=False)

    def __post_init__(self) -> None:
        for key, symbol in self.field_overrides.items():
            if not key.strip():
                raise ValueError("field override keys must be non-empty")
            self.registry.get(symbol)

    def unit_for(self, field_key: str, dimension: tuple[int, ...]) -> str:
        if field_key in self.field_overrides:
            selected = self.registry.get(self.field_overrides[field_key])
            if selected.dimension != tuple(dimension):
                raise ValueError(f"override for '{field_key}' has incompatible dimensions")
            return selected.symbol
        try:
            symbol = self.profile.defaults[tuple(dimension)]
        except KeyError as exc:
            raise ValueError(f"profile '{self.profile.profile_id}' has no default for dimension {dimension}") from exc
        selected = self.registry.get(symbol)
        if selected.dimension != tuple(dimension):
            raise ValueError("profile default has incompatible dimensions")
        return selected.symbol

    def display(self, field_key: str, quantity: Quantity) -> Quantity:
        return quantity.to(self.unit_for(field_key, quantity.dimension))

    def with_override(self, field_key: str, unit: str) -> "UnitDisplayPreferences":
        definition = self.registry.get(unit)
        # Validate against the field's known quantity when displaying; the profile
        # does not guess the field's dimension from its name.
        updated = dict(self.field_overrides)
        updated[field_key] = definition.symbol
        return UnitDisplayPreferences(self.profile, updated, self.registry)


SI_PROFILE = UnitSystemProfile(
    "si", "International System (SI)",
    {LENGTH: "m", MASS: "kg", TIME: "s", TEMPERATURE: "K",
     FORCE: "N", PRESSURE: "Pa", (0, 2, 0, 0, 0, 0, 0): "m2",
     (0, 3, 0, 0, 0, 0, 0): "m3", (0, 1, -1, 0, 0, 0, 0): "m/s"},
)
METRIC_ENGINEERING_PROFILE = UnitSystemProfile(
    "metric_engineering", "Metric engineering",
    {LENGTH: "mm", MASS: "kg", TIME: "s", TEMPERATURE: "degC",
     FORCE: "N", PRESSURE: "MPa", (0, 2, 0, 0, 0, 0, 0): "mm2",
     (0, 3, 0, 0, 0, 0, 0): "L", (0, 1, -1, 0, 0, 0, 0): "m/s"},
)
US_CUSTOMARY_PROFILE = UnitSystemProfile(
    "us_customary", "US customary",
    {LENGTH: "in", MASS: "lb", TIME: "s", TEMPERATURE: "degF",
     FORCE: "lbf", PRESSURE: "psi", (0, 2, 0, 0, 0, 0, 0): "in2",
     (0, 3, 0, 0, 0, 0, 0): "US_gal", (0, 1, -1, 0, 0, 0, 0): "ft/s"},
)
EUROPEAN_METRIC_PROFILE = UnitSystemProfile(
    "european_metric", "European metric",
    {LENGTH: "mm", MASS: "kg", TIME: "s", TEMPERATURE: "degC",
     FORCE: "N", PRESSURE: "bar", (0, 2, 0, 0, 0, 0, 0): "mm2",
     (0, 3, 0, 0, 0, 0, 0): "L", (0, 1, -1, 0, 0, 0, 0): "m/s"},
)
UK_IMPERIAL_PROFILE = UnitSystemProfile(
    "uk_imperial", "UK imperial",
    {LENGTH: "ft", MASS: "lb", TIME: "s", TEMPERATURE: "degF",
     FORCE: "lbf", PRESSURE: "psi", (0, 2, 0, 0, 0, 0, 0): "ft2",
     (0, 3, 0, 0, 0, 0, 0): "Imp_gal", (0, 1, -1, 0, 0, 0, 0): "ft/s"},
)
MARINE_HYBRID_PROFILE = UnitSystemProfile(
    "marine_hybrid", "Marine hybrid",
    {LENGTH: "m", MASS: "kg", TIME: "s", TEMPERATURE: "degC",
     FORCE: "N", PRESSURE: "bar", (0, 2, 0, 0, 0, 0, 0): "m2",
     (0, 3, 0, 0, 0, 0, 0): "L", (0, 1, -1, 0, 0, 0, 0): "m/s"},
)

BUILTIN_UNIT_PROFILES = {
    profile.profile_id: profile for profile in (
        SI_PROFILE, METRIC_ENGINEERING_PROFILE, US_CUSTOMARY_PROFILE,
        EUROPEAN_METRIC_PROFILE, UK_IMPERIAL_PROFILE, MARINE_HYBRID_PROFILE,
    )
}


@dataclass(frozen=True, slots=True)
class NominalSizeDesignation:
    """A standards-based trade designation (for example NPS 1 or DN 25).

    A nominal designation is not a physical length and must not be converted
    arithmetically to mm/in. Actual geometry belongs in a separate Quantity.
    """

    scheme: str
    designation: str
    standard_reference: str
    actual_outside_diameter: Quantity | None = None

    def __post_init__(self) -> None:
        if not self.scheme.strip() or not self.designation.strip():
            raise ValueError("nominal size scheme and designation must be non-empty")
        if not self.standard_reference.strip():
            raise ValueError("nominal size requires a standard/reference")
        if self.actual_outside_diameter is not None:
            if self.actual_outside_diameter.dimension != LENGTH:
                raise ValueError("actual outside diameter must have length dimension")


@dataclass(frozen=True, slots=True)
class VoiceUnitCommand:
    """Parsed intent from speech-to-text; this module does not perform speech recognition."""

    source_unit: str
    target_unit: str
    field_key: str | None = None


_UNIT_ALIASES = {
    "дюйм": "in", "дюйма": "in", "дюймы": "in", "дюймов": "in", "inch": "in", "inches": "in",
    "сантиметр": "cm", "сантиметра": "cm", "сантиметры": "cm", "сантиметров": "cm", "сантиметры": "cm", "centimeter": "cm", "centimeters": "cm", "centimetres": "cm",
    "миллиметр": "mm", "миллиметра": "mm", "миллиметры": "mm", "миллиметров": "mm", "millimeter": "mm", "millimeters": "mm", "millimetres": "mm",
    "метр": "m", "метра": "m", "метры": "m", "метров": "m", "meter": "m", "meters": "m", "metres": "m",
    "килограмм": "kg", "килограмма": "kg", "килограммы": "kg", "килограммов": "kg", "килограм": "kg", "kilogram": "kg", "kilograms": "kg",
    "фунт": "lb", "фунта": "lb", "фунты": "lb", "фунтов": "lb", "pound": "lb", "pounds": "lb",
    "литр": "L", "литра": "L", "литры": "L", "литров": "L", "литрa": "L", "liter": "L", "liters": "L", "litre": "L", "litres": "L",
    "галлон": "US_gal", "галлона": "US_gal", "галлоны": "US_gal", "галлонов": "US_gal", "gallon": "US_gal", "gallons": "US_gal",
    "имперский галлон": "Imp_gal", "имперских галлонов": "Imp_gal", "imperial gallon": "Imp_gal", "imperial gallons": "Imp_gal",
    "градус цельсия": "degC", "градусов цельсия": "degC", "градусы цельсия": "degC", "цельсия": "degC", "celsius": "degC",
    "градус фаренгейта": "degF", "градусов фаренгейта": "degF", "градусы фаренгейта": "degF", "фаренгейта": "degF", "fahrenheit": "degF",
}


def parse_voice_unit_command(transcript: str) -> VoiceUnitCommand:
    """Parse explicit 'convert X to Y' / 'переведи X в Y' speech transcripts."""
    normalized = " ".join(transcript.lower().strip().replace("ё", "е").split())
    patterns = (
        r"^(?:переведи|перевести|измени|преобразуй)\s+(.+?)\s+(?:в|на)\s+(.+?)(?:\s+для\s+(.+))?$",
        r"^(?:convert|change)\s+(.+?)\s+(?:to|into)\s+(.+?)(?:\s+for\s+(.+))?$",
    )
    match = next((re.search(pattern, normalized) for pattern in patterns if re.search(pattern, normalized)), None)
    if not match:
        raise ValueError("could not understand unit conversion command")
    source_text, target_text = match.group(1).strip(" .,!?:;"), match.group(2).strip(" .,!?:;")
    field_key = match.group(3).strip().replace(" ", ".") if match.group(3) else None
    source = _UNIT_ALIASES.get(source_text)
    target = _UNIT_ALIASES.get(target_text)
    if source is None or target is None:
        raise ValueError("unit name is not recognized; ask the user to choose an explicit unit")
    src_def = DEFAULT_UNIT_REGISTRY.get(source)
    dst_def = DEFAULT_UNIT_REGISTRY.get(target)
    if src_def.dimension != dst_def.dimension:
        raise ValueError("source and target units have incompatible dimensions")
    return VoiceUnitCommand(source, target, field_key)


def convert_by_voice(quantity: Quantity, command: VoiceUnitCommand) -> Quantity:
    """Apply a parsed conversion only when the selected value uses the stated source unit."""
    if quantity.unit != command.source_unit:
        raise ValueError(
            f"selected value is in '{quantity.unit}', not requested source unit '{command.source_unit}'"
        )
    return quantity.to(command.target_unit)
