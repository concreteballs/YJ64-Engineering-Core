import json
import unittest

from yj64_engineering_core.contracts import (
    ArtifactReference,
    EngineeringRequest,
    EngineeringResponse,
    GeometrySpec,
    LoadCase,
    SolverProvenance,
)


class EngineeringRequestContractTests(unittest.TestCase):
    def make_request(self):
        return EngineeringRequest(
            request_id="yacht-bracket-001",
            title="Bracket screening",
            objective="Check a preliminary bracket concept",
            geometry=GeometrySpec(
                geometry_type="plate",
                parameters={"width_m": 0.08, "thickness_m": 0.006},
            ),
            material={"name": "Example steel", "youngs_modulus_pa": 200e9},
            load_cases=(LoadCase(name="service", force_n=(0.0, 0.0, -1200.0)),),
            requirements=("Report maximum stress",),
            assumptions=("Static load",),
        )

    def test_request_json_round_trip(self):
        request = self.make_request()
        restored = EngineeringRequest.from_json(request.to_json())
        self.assertEqual(restored, request)
        self.assertEqual(json.loads(request.to_json())["contract_version"], "1.0")

    def test_rejects_non_finite_nested_geometry_value(self):
        with self.assertRaises(ValueError):
            GeometrySpec("plate", {"width_m": float("nan")})

    def test_rejects_non_si_units(self):
        with self.assertRaises(ValueError):
            EngineeringRequest(
                request_id="request-1",
                title="Test",
                objective="Test",
                units_system="imperial",
            )

    def test_rejects_json_nan_constant(self):
        with self.assertRaises(ValueError):
            EngineeringRequest.from_json(
                '{"request_id":"r1","title":"T","objective":"O","material":{"density":NaN}}'
            )

    def test_rejects_invalid_load_vector(self):
        with self.assertRaises(ValueError):
            LoadCase(name="bad", force_n=(1.0, 2.0))


class EngineeringResponseContractTests(unittest.TestCase):
    def test_result_serializes_with_provenance_and_artifact(self):
        response = EngineeringResponse(
            request_id="yacht-bracket-001",
            status="screening_only",
            provenance=SolverProvenance(
                solver_name="YJ64 reference solver",
                solver_version="0.1.0",
                method="linear_elastic_screening",
            ),
            values={"stress_pa": 42e6},
            units={"stress_pa": "Pa"},
            warnings=("Screening only",),
            artifacts=(
                ArtifactReference(
                    artifact_id="drawing-001",
                    media_type="image/svg+xml",
                    uri="workspace://artifacts/bracket.svg",
                ),
            ),
        )
        data = json.loads(response.to_json())
        self.assertEqual(data["provenance"]["method"], "linear_elastic_screening")
        self.assertEqual(data["artifacts"][0]["media_type"], "image/svg+xml")

    def test_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            EngineeringResponse(
                request_id="r1",
                status="looks-good",
                provenance=SolverProvenance("solver", "1", "method"),
            )

    def test_rejects_non_finite_result(self):
        with self.assertRaises(ValueError):
            EngineeringResponse(
                request_id="r1",
                status="completed",
                provenance=SolverProvenance("solver", "1", "method"),
                values={"answer": float("inf")},
            )

    def test_artifact_digest_must_be_sha256(self):
        with self.assertRaises(ValueError):
            ArtifactReference("artifact-1", "model/step", "workspace://part.step", "not-a-digest")


if __name__ == "__main__":
    unittest.main()
