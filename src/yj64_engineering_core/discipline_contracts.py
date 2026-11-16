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
class MaterialPropertyDatum:
    """Cross-pack property evidence; SI value and source context are explicit."""

    property_name: str
    value: float
    unit: str
    test_method: str
    source: str
    evidence_state: Literal["hypothesis", "predicted", "calculated", "literature", "measured"] = "hypothesis"
    source_date: str | None = None
    temperature_k: float | None = None
    uncertainty_absolute: float | None = None
    uncertainty_relative: float | None = None
    orientation: str | None = None
    product_direction: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("property_name", "unit", "test_method", "source"):
            _text(getattr(self, name), name)
        _finite(self.value, "value")
        if self.evidence_state not in {"hypothesis", "predicted", "calculated", "literature", "measured"}:
            raise ValueError("unsupported property evidence_state")
        for name in ("temperature_k", "uncertainty_absolute", "uncertainty_relative"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
                if name == "temperature_k" and value <= 0:
                    raise ValueError("temperature_k must be positive")
                if name != "temperature_k" and value < 0:
                    raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class StimulusResponseDatum:
    """Cross-pack field-response evidence for electric, magnetic or hybrid actuation."""

    mode: Literal["electric", "magnetic", "hybrid"]
    contraction_strain_fraction: float
    blocked_stress_pa: float
    electric_field_v_m: float | None = None
    magnetic_flux_density_t: float | None = None
    magnetic_field_strength_a_m: float | None = None
    response_time_s: float | None = None
    cycle_life: int | None = None
    temperature_range_k: tuple[float, float] | None = None
    reversible: bool = False
    evidence_state: Literal["hypothesis", "predicted", "calculated", "literature", "measured"] = "hypothesis"
    source_refs: tuple[str, ...] = ()
    test_conditions: str = ""

    def __post_init__(self) -> None:
        if self.mode not in {"electric", "magnetic", "hybrid"}:
            raise ValueError("mode must be electric, magnetic or hybrid")
        _finite(self.contraction_strain_fraction, "contraction_strain_fraction")
        if not 0 <= self.contraction_strain_fraction <= 1:
            raise ValueError("contraction_strain_fraction must be between 0 and 1")
        _finite(self.blocked_stress_pa, "blocked_stress_pa")
        if self.blocked_stress_pa < 0:
            raise ValueError("blocked_stress_pa cannot be negative")
        for name in ("electric_field_v_m", "magnetic_flux_density_t", "magnetic_field_strength_a_m", "response_time_s"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
                if value < 0:
                    raise ValueError(f"{name} cannot be negative")
        if self.mode == "electric" and self.electric_field_v_m is None:
            raise ValueError("electric response requires electric_field_v_m")
        if self.mode == "magnetic" and self.magnetic_flux_density_t is None and self.magnetic_field_strength_a_m is None:
            raise ValueError("magnetic response requires magnetic field data")
        if self.mode == "hybrid" and (
            self.electric_field_v_m is None or
            (self.magnetic_flux_density_t is None and self.magnetic_field_strength_a_m is None)
        ):
            raise ValueError("hybrid response requires electric and magnetic field data")
        if self.cycle_life is not None and (
            isinstance(self.cycle_life, bool) or not isinstance(self.cycle_life, int) or self.cycle_life < 0
        ):
            raise ValueError("cycle_life must be a non-negative integer")
        if self.temperature_range_k is not None:
            if len(self.temperature_range_k) != 2:
                raise ValueError("temperature_range_k must contain two values")
            low, high = self.temperature_range_k
            _finite(low, "temperature_range_k[0]")
            _finite(high, "temperature_range_k[1]")
            if low <= 0 or high < low:
                raise ValueError("temperature range must be positive and ordered")
        if self.evidence_state not in {"hypothesis", "predicted", "calculated", "literature", "measured"}:
            raise ValueError("unsupported stimulus evidence_state")
        if not all(isinstance(ref, str) and ref.strip() for ref in self.source_refs):
            raise ValueError("source_refs must contain non-empty strings")
        if self.evidence_state != "hypothesis" and not self.source_refs:
            raise ValueError("non-hypothesis stimulus evidence requires source_refs")
        if not isinstance(self.reversible, bool) or not isinstance(self.test_conditions, str):
            raise TypeError("reversible must be boolean and test_conditions must be a string")


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
    property_evidence: tuple[MaterialPropertyDatum, ...] = ()
    stimulus_responses: tuple[StimulusResponseDatum, ...] = ()

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
        if not all(isinstance(item, MaterialPropertyDatum) for item in self.property_evidence):
            raise TypeError("property_evidence must contain MaterialPropertyDatum records")
        if not all(isinstance(item, StimulusResponseDatum) for item in self.stimulus_responses):
            raise TypeError("stimulus_responses must contain StimulusResponseDatum records")
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
