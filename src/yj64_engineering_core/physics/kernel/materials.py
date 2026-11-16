"""Evidence-aware material records shared across all engineering disciplines.

No default strength, stiffness, density, fatigue or thermal values are invented.
Each measured/reported property retains its units, source, method, condition
and uncertainty so a solver can decide whether the evidence is applicable.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True)
class MaterialPropertyEvidence:
    """One property datum with enough context to judge its applicability.

    Values use SI units. The unit is explicit metadata, not an implicit
    conversion request. Multiple records for one property are allowed when
    test conditions, directions or sources differ.
    """

    property_name: str
    value: float
    unit: str
    test_method: str
    source: str
    source_date: str | None = None
    temperature_k: float | None = None
    orientation: str | None = None
    product_direction: str | None = None
    uncertainty_absolute: float | None = None
    uncertainty_relative: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("property_name", "unit", "test_method", "source"):
            _non_empty(getattr(self, name), name)
        _finite(self.value, "value")
        if self.source_date is not None:
            try:
                date.fromisoformat(self.source_date)
            except (TypeError, ValueError) as exc:
                raise ValueError("source_date must be an ISO date (YYYY-MM-DD)") from exc
        if self.temperature_k is not None:
            _finite(self.temperature_k, "temperature_k")
            if self.temperature_k <= 0:
                raise ValueError("temperature_k must be above absolute zero")
        for name in ("uncertainty_absolute", "uncertainty_relative"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
                if value < 0:
                    raise ValueError(f"{name} cannot be negative")
        for name in ("orientation", "product_direction", "notes"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string when supplied")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MaterialRecord:
    """A material identity; properties remain separate evidence records."""

    material_id: str
    name: str
    family: str
    grade: str | None = None
    product_form: str | None = None
    condition: str | None = None
    heat_treatment: str | None = None
    properties: tuple[MaterialPropertyEvidence, ...] = ()
    source_refs: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("material_id", "name", "family"):
            _non_empty(getattr(self, name), name)
        for name in ("grade", "product_form", "condition", "heat_treatment", "notes"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string when supplied")
        if not all(isinstance(item, MaterialPropertyEvidence) for item in self.properties):
            raise TypeError("properties must contain MaterialPropertyEvidence records")
        for collection_name, values in (("source_refs", self.source_refs), ("tags", self.tags)):
            if not all(isinstance(item, str) and item.strip() for item in values):
                raise ValueError(f"{collection_name} must contain non-empty strings")

    def property_evidence(self, property_name: str) -> tuple[MaterialPropertyEvidence, ...]:
        """Return all evidence for a property without silently choosing one."""
        _non_empty(property_name, "property_name")
        return tuple(item for item in self.properties if item.property_name == property_name)

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "properties": [item.to_dict() for item in self.properties],
        }


class MaterialLibrary:
    """Small in-memory registry; persistence belongs to the project data layer."""

    def __init__(self, records: Iterable[MaterialRecord] = ()) -> None:
        self._records: dict[str, MaterialRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: MaterialRecord) -> None:
        if not isinstance(record, MaterialRecord):
            raise TypeError("record must be a MaterialRecord")
        if record.material_id in self._records:
            raise ValueError(f"material_id already exists: {record.material_id}")
        self._records[record.material_id] = record

    def get(self, material_id: str) -> MaterialRecord:
        _non_empty(material_id, "material_id")
        try:
            return self._records[material_id]
        except KeyError as exc:
            raise KeyError(f"Unknown material_id: {material_id}") from exc

    def find_by_family(self, family: str) -> tuple[MaterialRecord, ...]:
        _non_empty(family, "family")
        return tuple(
            record for record in self._records.values()
            if record.family.casefold() == family.casefold()
        )

    def list_records(self) -> tuple[MaterialRecord, ...]:
        return tuple(self._records.values())

    def __len__(self) -> int:
        return len(self._records)
