"""Versioned, solver-neutral contracts shared by independent discipline packs.

These records describe candidates and requirements; they do not predict material
properties or imply that a candidate has been manufactured or validated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

DISCIPLINE_CONTRACT_VERSION = "1.0"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class CompositionComponent:
    """A constituent in a formulation; fraction is mass or volume fraction."""

    constituent_id: str
    role: str
    fraction: float
    basis: Literal["mass", "volume"]

    def __post_init__(self) -> None:
        _text(self.constituent_id, "constituent_id")
        _text(self.role, "role")
        _finite(self.fraction, "fraction")
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError("fraction must be between 0 and 1 inclusive")
        if self.basis not in ("mass", "volume"):
            raise ValueError("basis must be 'mass' or 'volume'")


@dataclass(frozen=True, slots=True)
class MicrostructureDescriptor:
    """Explicit, solver-neutral description; geometry-specific detail is optional."""

    architecture: str
    particle_size_m: float | None = None
    porosity_fraction: float | None = None
    orientation: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _text(self.architecture, "architecture")
        if self.particle_size_m is not None:
            _finite(self.particle_size_m, "particle_size_m")
            if self.particle_size_m <= 0:
                raise ValueError("particle_size_m must be positive")
        if self.porosity_fraction is not None:
            _finite(self.porosity_fraction, "porosity_fraction")
            if not 0 <= self.porosity_fraction <= 1:
                raise ValueError("porosity_fraction must be between 0 and 1")
        if self.orientation is not None and not isinstance(self.orientation, str):
            raise TypeError("orientation must be a string when supplied")


@dataclass(frozen=True, slots=True)
class MaterialCandidate:
    """A versioned formulation linked to the shared evidence-aware material record."""

    candidate_id: str
    revision: str
    material_id: str
    composition: tuple[CompositionComponent, ...]
    evidence_state: Literal[
        "hypothesis", "defined", "computationally_screened",
        "experimentally_characterized", "qualified"
    ] = "hypothesis"
    microstructure: MicrostructureDescriptor | None = None
    process_route: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("candidate_id", "revision", "material_id"):
            _text(getattr(self, name), name)
        if not self.composition:
            raise ValueError("composition must contain at least one constituent")
        if not all(isinstance(item, CompositionComponent) for item in self.composition):
            raise TypeError("composition entries must be CompositionComponent records")
        bases = {item.basis for item in self.composition}
        if len(bases) != 1:
            raise ValueError("all fractions in one composition must use the same basis")
        if not math.isclose(sum(item.fraction for item in self.composition), 1.0, abs_tol=1e-6):
            raise ValueError("composition fractions must sum to 1.0 within 1e-6")
        if self.evidence_state not in {
            "hypothesis", "defined", "computationally_screened",
            "experimentally_characterized", "qualified"
        }:
            raise ValueError("unsupported evidence_state")
        for collection in (self.process_route, self.source_refs, self.warnings):
            if not all(isinstance(item, str) and item.strip() for item in collection):
                raise ValueError("process_route, source_refs and warnings must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class PropertyConstraint:
    """A required property interval expressed in one declared unit."""

    property_name: str
    unit: str
    minimum: float | None = None
    maximum: float | None = None
    required: bool = True

    def __post_init__(self) -> None:
        _text(self.property_name, "property_name")
        _text(self.unit, "unit")
        if self.minimum is None and self.maximum is None:
            raise ValueError("at least one of minimum or maximum is required")
        if self.minimum is not None:
            _finite(self.minimum, "minimum")
        if self.maximum is not None:
            _finite(self.maximum, "maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")


@dataclass(frozen=True, slots=True)
class ActuatorMaterialRequest:
    """Material request sent by an actuator discipline to chemistry/materials."""

    request_id: str
    actuator_architecture: str
    target_mechanism: str
    operating_temperature_k: tuple[float, float]
    property_constraints: tuple[PropertyConstraint, ...]
    environment: str = "unspecified"
    duty_cycle_fraction: float | None = None
    notes: str = ""
    contract_version: str = DISCIPLINE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "actuator_architecture", "target_mechanism", "environment"):
            _text(getattr(self, name), name)
        if self.contract_version != DISCIPLINE_CONTRACT_VERSION:
            raise ValueError(f"unsupported contract_version: {self.contract_version}")
        if len(self.operating_temperature_k) != 2:
            raise ValueError("operating_temperature_k must contain (minimum, maximum)")
        low, high = self.operating_temperature_k
        _finite(low, "operating_temperature_k[0]")
        _finite(high, "operating_temperature_k[1]")
        if low <= 0 or high < low:
            raise ValueError("temperature range must be positive and ordered")
        if not self.property_constraints:
            raise ValueError("at least one property constraint is required")
        if not all(isinstance(item, PropertyConstraint) for item in self.property_constraints):
            raise TypeError("property_constraints must contain PropertyConstraint records")
        if self.duty_cycle_fraction is not None:
            _finite(self.duty_cycle_fraction, "duty_cycle_fraction")
            if not 0 <= self.duty_cycle_fraction <= 1:
                raise ValueError("duty_cycle_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class MaterialCandidateResponse:
    """Traceable response; empty candidates means no match, not a failed search."""

    request_id: str
    candidates: tuple[MaterialCandidate, ...] = ()
    rejected_candidate_ids: tuple[str, ...] = ()
    unresolved_constraints: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)
    producer_pack: str = "chemistry-molecular-design"
    contract_version: str = DISCIPLINE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.producer_pack, "producer_pack")
        if self.contract_version != DISCIPLINE_CONTRACT_VERSION:
            raise ValueError(f"unsupported contract_version: {self.contract_version}")
        if not all(isinstance(item, MaterialCandidate) for item in self.candidates):
            raise TypeError("candidates must contain MaterialCandidate records")
        for collection in (self.rejected_candidate_ids, self.unresolved_constraints, self.warnings):
            if not all(isinstance(item, str) and item.strip() for item in collection):
                raise ValueError("response metadata must contain non-empty strings")
