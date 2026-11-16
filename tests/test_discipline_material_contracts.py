import unittest

from yj64_engineering_core.chemistry import (
    CompositionComponent,
    MaterialCandidate,
    MaterialCandidateResponse,
    MicrostructureDescriptor,
)
from yj64_engineering_core.artificial_muscle import ActuatorMaterialRequest, PropertyConstraint


def candidate():
    return MaterialCandidate(
        candidate_id="magneto-polymer-001",
        revision="1",
        material_id="candidate-material-001",
        composition=(
            CompositionComponent("silicone-matrix", "matrix", 0.70, "volume"),
            CompositionComponent("iron-particles", "magnetic-filler", 0.30, "volume"),
        ),
        microstructure=MicrostructureDescriptor(
            architecture="particle-filled elastomer",
            particle_size_m=20e-6,
            orientation="field-aligned",
        ),
    )


class DisciplineMaterialContractTests(unittest.TestCase):
    def test_candidate_can_be_returned_to_actuator_pack(self):
        response = MaterialCandidateResponse(
            request_id="muscle-request-001",
            candidates=(candidate(),),
        )
        self.assertEqual(response.candidates[0].material_id, "candidate-material-001")
        self.assertEqual(response.contract_version, "1.0")

    def test_actuator_pack_can_request_material_properties(self):
        request = ActuatorMaterialRequest(
            request_id="muscle-request-001",
            actuator_architecture="fiber-bundle",
            target_mechanism="magnetoactive",
            operating_temperature_k=(273.15, 353.15),
            property_constraints=(
                PropertyConstraint("maximum_recoverable_strain", "1", minimum=0.10),
                PropertyConstraint("density", "kg/m3", maximum=2500),
            ),
            duty_cycle_fraction=0.5,
        )
        self.assertEqual(request.property_constraints[0].minimum, 0.10)
        self.assertEqual(request.contract_version, "1.0")

    def test_composition_rejects_mixed_fraction_basis(self):
        with self.assertRaisesRegex(ValueError, "same basis"):
            MaterialCandidate(
                candidate_id="bad",
                revision="1",
                material_id="bad-material",
                composition=(
                    CompositionComponent("a", "matrix", 0.5, "mass"),
                    CompositionComponent("b", "filler", 0.5, "volume"),
                ),
            )

    def test_composition_must_sum_to_one(self):
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            MaterialCandidate(
                candidate_id="bad",
                revision="1",
                material_id="bad-material",
                composition=(
                    CompositionComponent("a", "matrix", 0.6, "mass"),
                    CompositionComponent("b", "filler", 0.3, "mass"),
                ),
            )

    def test_temperature_range_must_be_ordered(self):
        with self.assertRaisesRegex(ValueError, "positive and ordered"):
            ActuatorMaterialRequest(
                request_id="bad",
                actuator_architecture="fiber",
                target_mechanism="electric",
                operating_temperature_k=(350, 300),
                property_constraints=(PropertyConstraint("strain", "1", minimum=0.1),),
            )

    def test_candidate_defaults_to_hypothesis_not_validated_material(self):
        self.assertEqual(candidate().evidence_state, "hypothesis")
        self.assertEqual(candidate().warnings, ())


if __name__ == "__main__":
    unittest.main()
