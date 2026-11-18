import json
import os
import unittest
from unittest.mock import patch

from yj64_engineering_core.automation.council_gateway import (
    CouncilGatewayClient,
    CouncilGatewayError,
    CouncilRequest,
    PROTOCOL_VERSION,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.raw[:limit]


class FakeOpener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        return FakeResponse(response)


class CouncilGatewayClientTests(unittest.TestCase):
    def request(self):
        return CouncilRequest(
            mode="consensus",
            title="Review proposed change",
            prompt="Assess the proposed implementation.",
            correlation_id="engineering-task-123",
            idempotency_key="idem-key-12345678",
            context={"repository": "concreteballs/YJ64-Engineering-Core"},
            evidence_refs=("https://github.com/concreteballs/YJ64-Engineering-Core",),
        )

    def client(self, opener):
        return CouncilGatewayClient(
            base_url="https://yj64.example",
            token="server-only-token",
            supabase_api_key="sb_publishable_test",
            opener=opener,
        )

    def test_submit_uses_machine_auth_and_idempotency_key(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "accepted",
        })
        result = self.client(opener).submit(self.request())
        request, _timeout = opener.requests[0]
        self.assertEqual(result["request_id"], "request-123")
        self.assertEqual(request.get_header("Authorization"), "Bearer server-only-token")
        self.assertEqual(request.get_header("Apikey"), "sb_publishable_test")
        self.assertEqual(request.get_header("Idempotency-key"), "idem-key-12345678")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["mode"], "consensus")
        self.assertEqual(body["limits"]["minimum_critique_rounds"], 1)

    def test_constructor_requires_supabase_api_key(self):
        with self.assertRaises(ValueError):
            CouncilGatewayClient(base_url="https://yj64.example", token="server-only-token", supabase_api_key="")

    def test_from_environment_sends_supabase_publishable_key(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "running",
        })
        environment = {
            "YJ64_COUNCIL_API_URL": "https://yj64.example",
            "YJ64_COUNCIL_AGENT_TOKEN": "server-only-token",
            "YJ64_COUNCIL_SUPABASE_API_KEY": "sb_publishable_from_env",
            "YJ64_COUNCIL_AGENT_ID": "yj64-engineering-core",
        }
        with patch.dict(os.environ, environment, clear=True):
            client = CouncilGatewayClient.from_environment(opener=opener)
            client.get_status("request-123")
        request, _timeout = opener.requests[0]
        self.assertEqual(request.get_header("Apikey"), "sb_publishable_from_env")
        self.assertEqual(request.get_header("Authorization"), "Bearer server-only-token")

    def test_from_environment_fails_closed_without_supabase_api_key(self):
        environment = {
            "YJ64_COUNCIL_API_URL": "https://yj64.example",
            "YJ64_COUNCIL_AGENT_TOKEN": "server-only-token",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(RuntimeError):
                CouncilGatewayClient.from_environment()

    def test_status_requires_matching_request_and_session_ids(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "running",
            "progress": {"round": 2},
        })
        result = self.client(opener).get_status("request-123")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["progress"]["round"], 2)

    def test_result_preserves_substantive_outcome_and_dissent(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "completed",
            "outcome": "qualified_consensus",
            "summary": "Agreement with one unresolved limitation.",
            "claims": [{"claim_id": "claim-1", "statement": "A", "epistemic_type": "inference", "reasoning": "Derived from evidence.", "evidence_refs": ["evidence-1"]}],
            "participant_positions": [{"participant_id": "P1", "position": "agree", "rationale": "Evidence supports the claim."}],
            "dissent": [{"participant_id": "P2", "reason": "missing test"}],
            "evidence": [{"evidence_id": "evidence-1", "reference": "artifact://evidence/1", "description": "Test artifact", "evidence_type": "artifact"}],
            "unresolved_questions": ["Does the test cover edge case B?"],
        })
        result = self.client(opener).get_result("request-123", "session-123")
        self.assertEqual(result["outcome"], "qualified_consensus")
        self.assertEqual(result["dissent"][0]["participant_id"], "P2")

    def test_rejects_result_for_another_session(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "other-session",
            "status": "completed",
            "outcome": "consensus",
            "summary": "Done",
        })
        with self.assertRaises(CouncilGatewayError):
            self.client(opener).get_result("request-123", "session-123")

    def test_rejects_unknown_outcome(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "completed",
            "outcome": "forced_agreement",
            "summary": "Done",
        })
        with self.assertRaises(CouncilGatewayError):
            self.client(opener).get_result("request-123", "session-123")

    def test_rejects_claim_without_epistemic_classification(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "completed",
            "outcome": "consensus",
            "summary": "Done",
            "claims": [{"claim_id": "c1", "statement": "A", "epistemic_type": "guess", "reasoning": "", "evidence_refs": []}],
        })
        with self.assertRaises(CouncilGatewayError):
            self.client(opener).get_result("request-123", "session-123")

    def test_rejects_secret_fields_in_context(self):
        request = CouncilRequest(
            mode="consensus",
            title="Review",
            prompt="Prompt",
            correlation_id="task-12345678",
            idempotency_key="idem-key-12345678",
            context={"api_key": "must-not-leave-this-worker"},
        )
        with self.assertRaises(ValueError):
            request.to_payload("yj64-engineering-core")

    def test_optional_voting_controls_are_explicit_and_bounded(self):
        request = CouncilRequest(
            mode="consensus",
            title="Review",
            prompt="Prompt",
            correlation_id="task-12345678",
            idempotency_key="idem-key-12345678",
            voting_enabled=True,
            weighted_voting_enabled=True,
        )
        payload = request.to_payload("yj64-engineering-core")
        self.assertEqual(payload["voting"], {"enabled": True, "weighted": True})
        self.assertTrue(payload["limits"]["allow_early_stop"])

    def test_weighted_voting_cannot_be_enabled_without_voting(self):
        request = CouncilRequest(
            mode="consensus",
            title="Review",
            prompt="Prompt",
            correlation_id="task-12345678",
            idempotency_key="idem-key-12345678",
            weighted_voting_enabled=True,
        )
        with self.assertRaises(ValueError):
            request.to_payload("yj64-engineering-core")

    def test_rejects_private_individual_ballots_in_result(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "completed",
            "outcome": "consensus",
            "summary": "Done",
            "voting_summary": {"enabled": True, "ballots": [{"participant_id": "P1", "vote": "FOR"}]},
        })
        with self.assertRaises(CouncilGatewayError):
            self.client(opener).get_result("request-123", "session-123")

    def test_api_routes_can_be_mapped_to_the_agreed_application_contract(self):
        opener = FakeOpener({
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "request-123",
            "session_id": "session-123",
            "status": "running",
        })
        client = CouncilGatewayClient(
            base_url="https://yj64.example",
            token="server-only-token",
            supabase_api_key="sb_publishable_test",
            opener=opener,
            status_path_template="/v2/native-council/jobs/{request_id}/state",
        )
        client.get_status("request-123")
        self.assertTrue(opener.requests[0][0].full_url.endswith("/v2/native-council/jobs/request-123/state"))

    def test_api_route_templates_cannot_change_the_configured_origin(self):
        with self.assertRaises(ValueError):
            CouncilGatewayClient(
                base_url="https://yj64.example",
                token="token",
                supabase_api_key="sb_publishable_test",
                status_path_template="https://attacker.example/{request_id}",
            )

    def test_rejects_plain_http_by_default(self):
        with self.assertRaises(ValueError):
            CouncilGatewayClient(base_url="http://yj64.example", token="token", supabase_api_key="sb_publishable_test")

    def test_request_limits_are_validated(self):
        request = CouncilRequest(
            mode="consensus",
            title="Review",
            prompt="Prompt",
            correlation_id="task-12345678",
            idempotency_key="idem-key-12345678",
            max_rounds=99,
        )
        with self.assertRaises(ValueError):
            request.to_payload("yj64-engineering-core")


if __name__ == "__main__":
    unittest.main()
