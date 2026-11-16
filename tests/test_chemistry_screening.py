"""Tests for evidence-aware chemistry formulation screening."""
import unittest

from yj64_engineering_core.chemistry.screening import (
    ChemistryCandidate,
    ChemistryScreeningEngine,
    StimulusResponseEvidence,
)
from yj64_engineering_core.discipline_contracts import (
    ActuatorMaterialRequest,
    CompositionComponent,
    MaterialCandidate,
    PropertyConstraint,
)
from yj64_engineering_core.physics.kernel.materials import (
    MaterialPropertyEvidence,
    MaterialRecord,
)


def make_candidate(*, mode="electric", evidence_state="measured", reversible=True,
                   properties=None, source_refs=("lab:test-001",)):
    formulation = MaterialCandidate(
        candidate_id="candidate-001",
        revision="1",
        material_id="material-001",
        composition=(
            CompositionComponent("polymer-matrix", "matrix", 0.7, "mass"),
            CompositionComponent("functional-filler", "active filler", 0.3, "mass"),
        ),
        evidence_state="defined",
    )
    record = MaterialRecord(
        material_id="material-001",
        name="Test formulation",
        family="polymer_composite",
        properties=tuple(properties or (
            MaterialPropertyEvidence(
                property_name="density",
                value=1200.0,
                unit="kg/m3",
                test_method="mass-volume measurement",
                source="test dataset",
                evidence_state="measured",
            ),
        )),
    )
    response = StimulusResponseEvidence(
        mode=mode,
        contraction_strain_fraction=0.05,
        blocked_stress_pa=100000.0,
        electric_field_v_m=2.0e6 if mode in {"electric", "hybrid"} else None,
        magnetic_flux_density_t=0.4 if mode in {"magnetic", "hybrid"} else None,
        reversible=reversible,
        evidence_state=evidence_state,
        source_refs=source_refs if evidence_state != "hypothesis" else (),
        test_conditions="23 C, dry specimen, quasi-static",
    )
    return ChemistryCandidate(formulation, record, (response,))


def make_request(mechanism="electric_field", constraints=None):
    return ActuatorMaterialRequest(
        request_id="request-001",
        actuator_architecture="fiber bundle",
        target_mechanism=mechanism,
        operating_temperature_k=(293.15, 333.15),
        property_constraints=tuple(constraints or (
            PropertyConstraint("density", "kg/m3", maximum=1500.0),
        )),
    )


class ChemistryScreeningTests(unittest.TestCase):
    def setUp(self):
        self.engine = ChemistryScreeningEngine()

    def test_measured_electric_candidate_passes(self):
        candidate = make_candidate()
        report = self.engine.screen(make_request(), (candidate,))
        self.assertEqual(report.candidates[0].candidate_id, "candidate-001")
        self.assertEqual(report.rejected, ())
        self.assertEqual(report.unresolved, ())

    def test_property_outside_limit_rejects_candidate(self):
        candidate = make_candidate(properties=(
            MaterialPropertyEvidence("density", 1800.0, "kg/m3", "measurement", "dataset"),
        ))
        report = self.engine.screen(make_request(), (candidate,))
        self.assertEqual(report.rejected[0].candidate_id, "candidate-001")

    def test_missing_required_property_is_unresolved(self):
        candidate = make_candidate(properties=())
        report = self.engine.screen(make_request(), (candidate,))
        self.assertEqual(report.unresolved[0].candidate_id, "candidate-001")

    def test_hybrid_requires_explicit_hybrid_evidence(self):
        candidate = make_candidate(mode="electric")
        report = self.engine.screen(make_request("hybrid_electric_magnetic"), (candidate,))
        self.assertEqual(report.unresolved[0].candidate_id, "candidate-001")

    def test_electric_and_magnetic_records_are_not_combined_as_hybrid(self):
        candidate = make_candidate(mode="electric")
        magnetic = StimulusResponseEvidence(
            mode="magnetic",
            contraction_strain_fraction=0.02,
            blocked_stress_pa=50000.0,
            magnetic_flux_density_t=0.3,
            evidence_state="measured",
            source_refs=("lab:mag-001",),
            test_conditions="separate magnetic test",
        )
        candidate = ChemistryCandidate(
            candidate.formulation, candidate.material_record,
            (candidate.stimulus_responses[0], magnetic),
        )
        report = self.engine.screen(make_request("hybrid"), (candidate,))
        self.assertEqual(report.unresolved[0].candidate_id, "candidate-001")

    def test_unit_mismatch_is_not_silently_converted(self):
        candidate = make_candidate(properties=(
            MaterialPropertyEvidence("density", 1.2, "g/cm3", "measurement", "dataset"),
        ))
        report = self.engine.screen(make_request(), (candidate,))
        self.assertIn("no implicit conversion", report.unresolved[0].unresolved_constraints[0])

    def test_hypothesis_is_not_reported_as_measured(self):
        candidate = make_candidate(evidence_state="hypothesis")
        report = self.engine.screen(make_request(), (candidate,))
        self.assertEqual(report.candidates[0].candidate_id, "candidate-001")
        self.assertTrue(any("hypothesis" in warning for warning in report.candidates[0].warnings))

    def test_invalid_hybrid_field_definition_is_rejected(self):
        with self.assertRaises(ValueError):
            StimulusResponseEvidence(
                mode="hybrid",
                contraction_strain_fraction=0.01,
                blocked_stress_pa=1000.0,
                electric_field_v_m=1e6,
            )

    def test_contract_response_preserves_candidate_and_unresolved_reason(self):
        candidate = make_candidate()
        response = self.engine.screen(make_request(), (candidate,)).to_contract_response((candidate,))
        self.assertEqual(response.candidates[0].candidate_id, "candidate-001")
        self.assertEqual(response.request_id, "request-001")
        self.assertEqual(response.candidates[0].property_evidence[0].evidence_state, "measured")
        self.assertEqual(response.candidates[0].stimulus_responses[0].mode, "electric")
        self.assertEqual(response.candidates[0].stimulus_responses[0].electric_field_v_m, 2.0e6)


if __name__ == "__main__":
    unittest.main()
