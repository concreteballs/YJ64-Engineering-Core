import importlib.util
import io
import json
import os
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "api" / "discovery.py"
SPEC = importlib.util.spec_from_file_location("yj64_discovery_api", MODULE_PATH)
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


class NonClosingBytesIO(io.BytesIO):
    def close(self):
        self.flush()


class FakeConnection:
    def __init__(self, request_bytes):
        self.input = io.BytesIO(request_bytes)
        self.output = NonClosingBytesIO()

    def makefile(self, mode, buffering=None):
        return self.input if "r" in mode else self.output

    def close(self):
        pass


def send_request(method, path, body=b"", token=None):
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: localhost",
        "Content-Type: application/json",
        f"Content-Length: {len(body)}",
        "Connection: close",
    ]
    if token is not None:
        headers.append(f"Authorization: Bearer {token}")
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body
    connection = FakeConnection(raw)
    API.handler(connection, ("127.0.0.1", 12345), object())
    response = connection.output.getvalue()
    header, _, payload = response.partition(b"\r\n\r\n")
    status = int(header.split(b" ")[1])
    return status, json.loads(payload.decode("utf-8"))


class AgentDiscoveryApiTests(unittest.TestCase):
    def setUp(self):
        self.previous_token = os.environ.get("YJ64_AGENT_API_TOKEN")
        os.environ["YJ64_AGENT_API_TOKEN"] = "test-secret"

    def tearDown(self):
        if self.previous_token is None:
            os.environ.pop("YJ64_AGENT_API_TOKEN", None)
        else:
            os.environ["YJ64_AGENT_API_TOKEN"] = self.previous_token

    def payload(self):
        return {
            "schema": "yj64.agent-sourcing-request.v1",
            "request_id": "api-test-1",
            "agent_id": "materials-agent",
            "task_description": "Find a polymer candidate",
            "destination": {
                "location_id": "dest-1", "name": "Destination",
                "country_code": "ES", "currency": "EUR",
                "latitude": 36.72, "longitude": -4.42,
            },
            "location_mode": "map",
            "categories": [{
                "category_id": "polymers", "label": "Polymers",
                "search_terms": ["silicone elastomer"],
            }],
            "market_scopes": ["local", "china"],
            "required_quantity": 2,
            "quantity_unit": "kg",
            "technical_requirements": [
                {"property_name": "elongation", "unit": "%", "minimum": 100}
            ],
            "maximum_total_budget": 100,
            "budget_currency": "EUR",
        }

    def test_rejects_missing_or_wrong_bearer_token(self):
        body = json.dumps(self.payload()).encode()
        status, response = send_request("POST", "/api/discovery", body, token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(response["error"], "unauthorized")

    def test_returns_agent_authored_search_plan(self):
        body = json.dumps(self.payload()).encode()
        status, response = send_request("POST", "/api/discovery", body, token="test-secret")
        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "planned")
        self.assertEqual(response["request"]["agent_id"], "materials-agent")
        self.assertEqual(
            {task["market_scope"] for task in response["plan"]["tasks"]},
            {"local", "china"},
        )
        self.assertEqual(response["plan"]["required_quantity"], 2)
        self.assertFalse(response["limitations"] == [])

    def test_rejects_invalid_agent_payload(self):
        body = json.dumps({"schema": "wrong"}).encode()
        status, response = send_request("POST", "/api/discovery", body, token="test-secret")
        self.assertEqual(status, 422)
        self.assertEqual(response["error"], "invalid_agent_request")


if __name__ == "__main__":
    unittest.main()
