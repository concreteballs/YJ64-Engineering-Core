"""Evidence-aware formulation and responsive-material screening.

This is a deterministic candidate-management layer, not a molecular generator,
reaction predictor or multiphysics solver. It only evaluates supplied evidence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, Sequence

from ..discipline_contracts import (
    ActuatorMaterialRequest,
    MaterialCandidate,
    MaterialCandidateResponse,
    MaterialPropertyDatum,
    StimulusResponseDatum,
)
from ..physics.kernel.materials import MaterialRecord

StimulusMode = Literal["electric", "magnetic", "hybrid"]
EvidenceState = Literal["hypothesis", "predicted", "calculated", "literature", "measured"]


def _finite(value: float, name: str, *, minimum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


@dataclass(frozen=True, slots=True)
class StimulusResponseEvidence:
    """Measured/reported response of a material under a declared applied field.

    Field values use SI: electric field V/m; magnetic flux density T and/or
    magnetic field strength A/m. For hybrid response both electric and at
    least one magnetic field measure are required. Strain is shortening as a
    positive fraction of the original gauge length.
    """

    mode: StimulusMode
    contraction_strain_fraction: float
    blocked_stress_pa: float
    electric_field_v_m: float | None = None
    magnetic_flux_density_t: float | None = None
    magnetic_field_strength_a_m: float | None = None
    response_time_s: float | None = None
    cycle_life: int | None = None
    temperature_range_k: tuple[float, float] | None = None
    reversible: bool = False
    evidence_state: EvidenceState = "hypothesis"
    source_refs: tuple[str, ...] = ()
    test_conditions: str = ""

    def __post_init__(self) -> None:
        if self.mode not in {"electric", "magnetic", "hybrid"}:
            raise ValueError("mode must be electric, magnetic or hybrid")
        _finite(self.contraction_strain_fraction, "contraction_strain_fraction", minimum=0.0)
        if self.contraction_strain_fraction > 1.0:
            raise ValueError("contraction_strain_fraction cannot exceed 1")
        _finite(self.blocked_stress_pa, "blocked_stress_pa", minimum=0.0)
        for name in ("electric_field_v_m", "magnetic_flux_density_t", "magnetic_field_strength_a_m", "response_time_s"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name, minimum=0.0)
        if self.mode == "electric" and self.electric_field_v_m is None:
            raise ValueError("electric response requires electric_field_v_m")
        if self.mode == "magnetic" and self.magnetic_flux_density_t is None and self.magnetic_field_strength_a_m is None:
            raise ValueError("magnetic response requires magnetic flux density or field strength")
        if self.mode == "hybrid":
            if self.electric_field_v_m is None:
                raise ValueError("hybrid response requires electric_field_v_m")
            if self.magnetic_flux_density_t is None and self.magnetic_field_strength_a_m is None:
                raise ValueError("hybrid response requires magnetic flux density or field strength")
        if self.cycle_life is not None:
            if isinstance(self.cycle_life, bool) or not isinstance(self.cycle_life, int) or self.cycle_life < 0:
                raise ValueError("cycle_life must be a non-negative integer")
        if self.temperature_range_k is not None:
            if len(self.temperature_range_k) != 2:
                raise ValueError("temperature_range_k must contain two values")
            low, high = self.temperature_range_k
            _finite(low, "temperature_range_k[0]", minimum=0.0)
            _finite(high, "temperature_range_k[1]", minimum=0.0)
            if low == 0 or high < low:
                raise ValueError("temperature range must be positive and ordered")
        if self.evidence_state not in {"hypothesis", "predicted", "calculated", "literature", "measured"}:
            raise ValueError("unsupported evidence_state")
        if not all(isinstance(ref, str) and ref.strip() for ref in self.source_refs):
            raise ValueError("source_refs must contain non-empty strings")
        if self.evidence_state != "hypothesis" and not self.source_refs:
            raise ValueError("non-hypothesis evidence requires at least one source_ref")
        if not isinstance(self.reversible, bool):
            raise TypeError("reversible must be boolean")
        if not isinstance(self.test_conditions, str):
            raise TypeError("test_conditions must be a string")


@dataclass(frozen=True, slots=True)
class ChemistryCandidate:
    """A formulation linked to the shared material identity and response data."""

    formulation: MaterialCandidate
    material_record: MaterialRecord
    stimulus_responses: tuple[StimulusResponseEvidence, ...] = ()
    hazard_notes: tuple[str, ...] = ()
    process_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.formulation, MaterialCandidate):
            raise TypeError("formulation must be a MaterialCandidate")
        if not isinstance(self.material_record, MaterialRecord):
            raise TypeError("material_record must be a MaterialRecord")
        if self.formulation.material_id != self.material_record.material_id:
            raise ValueError("formulation.material_id must match material_record.material_id")
        if not all(isinstance(item, StimulusResponseEvidence) for item in self.stimulus_responses):
            raise TypeError("stimulus_responses must contain StimulusResponseEvidence")
        for name, values in (("hazard_notes", self.hazard_notes), ("process_notes", self.process_notes)):
            if not all(isinstance(item, str) and item.strip() for item in values):
                raise ValueError(f"{name} must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class CandidateScreeningResult:
    candidate_id: str
    disposition: Literal["candidate", "rejected", "unresolved"]
    matching_stimulus_modes: tuple[str, ...]
    passed_constraints: tuple[str, ...]
    failed_constraints: tuple[str, ...]
    unresolved_constraints: tuple[str, ...]
    evidence_states: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChemistryScreeningReport:
    request_id: str
    results: tuple[CandidateScreeningResult, ...]
    engine_version: str = "0.1.0"

    @property
    def candidates(self) -> tuple[CandidateScreeningResult, ...]:
        return tuple(item for item in self.results if item.disposition == "candidate")

    @property
    def rejected(self) -> tuple[CandidateScreeningResult, ...]:
        return tuple(item for item in self.results if item.disposition == "rejected")

    @property
    def unresolved(self) -> tuple[CandidateScreeningResult, ...]:
        return tuple(item for item in self.results if item.disposition == "unresolved")

    def to_contract_response(self, formulations: Sequence[ChemistryCandidate]) -> MaterialCandidateResponse:
        by_id = {item.formulation.candidate_id: item for item in formulations}

        def enriched(candidate_id: str) -> MaterialCandidate:
            source = by_id[candidate_id]
            property_evidence = tuple(
                MaterialPropertyDatum(
                    property_name=item.property_name,
                    value=item.value,
                    unit=item.unit,
                    test_method=item.test_method,
                    source=item.source,
                    evidence_state=item.evidence_state,
                    source_date=item.source_date,
                    temperature_k=item.temperature_k,
                    uncertainty_absolute=item.uncertainty_absolute,
                    uncertainty_relative=item.uncertainty_relative,
                    orientation=item.orientation,
                    product_direction=item.product_direction,
                    notes=item.notes,
                )
                for item in source.material_record.properties
            )
            stimulus_responses = tuple(
                StimulusResponseDatum(
                    mode=item.mode,
                    contraction_strain_fraction=item.contraction_strain_fraction,
                    blocked_stress_pa=item.blocked_stress_pa,
                    electric_field_v_m=item.electric_field_v_m,
                    magnetic_flux_density_t=item.magnetic_flux_density_t,
                    magnetic_field_strength_a_m=item.magnetic_field_strength_a_m,
                    response_time_s=item.response_time_s,
                    cycle_life=item.cycle_life,
                    temperature_range_k=item.temperature_range_k,
                    reversible=item.reversible,
                    evidence_state=item.evidence_state,
                    source_refs=item.source_refs,
                    test_conditions=item.test_conditions,
                )
                for item in source.stimulus_responses
            )
            return replace(
                source.formulation,
                property_evidence=property_evidence,
                stimulus_responses=stimulus_responses,
            )

        accepted = tuple(enriched(item.candidate_id) for item in self.candidates)
        rejected_ids = tuple(item.candidate_id for item in self.rejected)
        unresolved = tuple(
            f"{item.candidate_id}: {reason}"
            for item in self.unresolved
            for reason in item.unresolved_constraints
        )
        warnings = tuple(
            f"{item.candidate_id}: {warning}"
            for item in self.results
            for warning in item.warnings
        )
        return MaterialCandidateResponse(
            request_id=self.request_id,
            candidates=accepted,
            rejected_candidate_ids=rejected_ids,
            unresolved_constraints=unresolved,
            warnings=warnings,
        )


class ChemistryScreeningEngine:
    """Screen explicitly supplied formulations against actuator requirements."""

    name = "YJ64 evidence-aware chemistry screening"
    version = "0.1.0"

    @staticmethod
    def _requested_mode(mechanism: str) -> StimulusMode | None:
        normalized = mechanism.strip().casefold().replace("-", "_").replace(" ", "_")
        aliases = {
            "electric": "electric",
            "electric_field": "electric",
            "electroactive": "electric",
            "electroactive_polymer": "electric",
            "dielectric_elastomer": "electric",
            "magnetic": "magnetic",
            "magnetic_field": "magnetic",
            "magnetostrictive": "magnetic",
            "magnetoactive": "magnetic",
            "hybrid": "hybrid",
            "hybrid_electric_magnetic": "hybrid",
            "electric_and_magnetic": "hybrid",
        }
        return aliases.get(normalized)  # Unknown mechanisms stay unresolved.

    @staticmethod
    def _constraint_result(candidate: ChemistryCandidate, property_name: str, unit: str,
                           minimum: float | None, maximum: float | None) -> tuple[str, str | None]:
        evidence = candidate.material_record.property_evidence(property_name)
        if not evidence:
            return "unresolved", f"{property_name} ({unit}): no evidence supplied"
        exact_unit = tuple(item for item in evidence if item.unit == unit)
        if not exact_unit:
            units = ", ".join(sorted({item.unit for item in evidence}))
            return "unresolved", f"{property_name}: requested {unit}, available {units}; no implicit conversion"
        if len(exact_unit) != 1:
            return "unresolved", f"{property_name} ({unit}): {len(exact_unit)} evidence records; conditions must be disambiguated"
        datum = exact_unit[0]
        if minimum is not None and datum.value < minimum:
            return "failed", f"{property_name}: {datum.value} {unit} is below {minimum} {unit}"
        if maximum is not None and datum.value > maximum:
            return "failed", f"{property_name}: {datum.value} {unit} exceeds {maximum} {unit}"
        return "passed", None

    def screen(self, request: ActuatorMaterialRequest,
               candidates: Sequence[ChemistryCandidate]) -> ChemistryScreeningReport:
        if not isinstance(request, ActuatorMaterialRequest):
            raise TypeError("request must be an ActuatorMaterialRequest")
        if not all(isinstance(item, ChemistryCandidate) for item in candidates):
            raise TypeError("candidates must contain ChemistryCandidate records")
        mode = self._requested_mode(request.target_mechanism)
        results: list[CandidateScreeningResult] = []
        seen_ids: set[str] = set()

        for candidate in candidates:
            formulation = candidate.formulation
            if formulation.candidate_id in seen_ids:
                raise ValueError(f"duplicate candidate_id: {formulation.candidate_id}")
            seen_ids.add(formulation.candidate_id)
            warnings = list(formulation.warnings) + list(candidate.hazard_notes)
            warnings.extend(candidate.process_notes)
            matching = tuple(
                item for item in candidate.stimulus_responses
                if mode is not None and item.mode == mode
            )
            unresolved: list[str] = []
            failed: list[str] = []
            passed: list[str] = []

            if mode is None:
                unresolved.append(f"unsupported or unspecified target mechanism: {request.target_mechanism}")
            elif not matching:
                unresolved.append(f"no {mode} stimulus-response evidence supplied")

            for constraint in request.property_constraints:
                outcome, detail = self._constraint_result(
                    candidate, constraint.property_name, constraint.unit,
                    constraint.minimum, constraint.maximum,
                )
                label = f"{constraint.property_name} [{constraint.unit}]"
                if outcome == "passed":
                    passed.append(label)
                elif outcome == "failed":
                    failed.append(label)
                    if detail:
                        warnings.append(detail)
                elif constraint.required:
                    unresolved.append(detail or label)
                else:
                    warnings.append(detail or f"optional property unresolved: {label}")

            for response in matching:
                if response.evidence_state in {"hypothesis", "predicted"}:
                    warnings.append(
                        f"{response.mode} response is {response.evidence_state}, not experimentally established"
                    )
                if not response.reversible:
                    warnings.append(f"{response.mode} response is not documented as reversible")
                if not response.test_conditions:
                    warnings.append(f"{response.mode} response has no test-condition description")

            if failed:
                disposition = "rejected"
            elif unresolved:
                disposition = "unresolved"
            else:
                disposition = "candidate"

            results.append(CandidateScreeningResult(
                candidate_id=formulation.candidate_id,
                disposition=disposition,
                matching_stimulus_modes=tuple(item.mode for item in matching),
                passed_constraints=tuple(passed),
                failed_constraints=tuple(failed),
                unresolved_constraints=tuple(unresolved),
                evidence_states=tuple(item.evidence_state for item in matching),
                warnings=tuple(warnings),
            ))

        return ChemistryScreeningReport(request_id=request.request_id, results=tuple(results))
