import json
import unittest

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
            evidence_refs=("https://github.com/concreteballs/YJ64-Engineering-Core"),
        )

    def client(self, opener):
        return CouncilGatewayClient(
            base_url="https://yj64.example",
            token="server-only-token",
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
        self.assertEqual(request.get_header("Idempotency-key"), "idem-key-12345678")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["mode"], "consensus")
        self.assertEqual(body["limits"]["minimum_critique_rounds"], 1)

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
            "claims": [{"claim": "A", "kind": "inference"}],
            "participant_positions": [{"participant": "P1", "position": "agree"}],
            "dissent": [{"participant": "P2", "reason": "missing test"}],
            "evidence": [{"ref": "artifact://evidence/1"}],
            "unresolved_questions": ["Does the test cover edge case B?"],
        })
        result = self.client(opener).get_result("request-123", "session-123")
        self.assertEqual(result["outcome"], "qualified_consensus")
        self.assertEqual(result["dissent"][0]["participant"], "P2")

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

    def test_rejects_plain_http_by_default(self):
        with self.assertRaises(ValueError):
            CouncilGatewayClient(base_url="http://yj64.example", token="token")

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
