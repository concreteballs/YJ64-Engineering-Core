import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "api" / "index.py"
SPEC = importlib.util.spec_from_file_location("yj64_ci_ingress_api", MODULE_PATH)
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

    def sendall(self, data):
        self.output.write(data)

    def close(self):
        pass


def send_request(payload, token="test-secret"):
    body = json.dumps(payload).encode()
    headers = [
        "POST /api HTTP/1.1", "Host: localhost",
        "Content-Type: application/json", f"Content-Length: {len(body)}",
        "Connection: close", f"Authorization: Bearer {token}",
    ]
    raw = ("\r\n".join(headers) + "\r\n\r\n").encode() + body
    connection = FakeConnection(raw)
    API.handler(connection, ("127.0.0.1", 12345), object())
    response = connection.output.getvalue()
    header, _, body = response.partition(b"\r\n\r\n")
    return int(header.split(b" ")[1]), json.loads(body.decode())


class CiWebhookIngressTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "YJ64_CI_WEBHOOK_SECRET": "test-secret",
            "YJ64_DATABASE_URL": "postgresql://test",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def payload(self):
        return {
            "event": "yj64.ci.completed",
            "repository": "concreteballs/YJ64-Engineering-Core",
            "workflow": "Python tests",
            "run_id": 123,
            "run_attempt": 1,
            "conclusion": "success",
            "commit_sha": "a" * 40,
            "branch": "main",
            "run_url": "https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/123",
        }

    def test_persists_valid_event_and_returns_queue_state(self):
        class FakeStore:
            def __init__(self, database_url):
                self.database_url = database_url

            def record_ci_event(self, event):
                self.event = event
                return {"accepted": True, "duplicate": False, "event_id": 9, "task_enqueued": True}

        with patch.object(API, "PostgresCycleStore", FakeStore):
            status, result = send_request(self.payload())
        self.assertEqual(status, 202)
        self.assertTrue(result["task_enqueued"])
        self.assertEqual(result["event_id"], 9)

    def test_rejects_wrong_token(self):
        status, result = send_request(self.payload(), token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(result["error"], "unauthorized")


    def test_sqlstate_is_checked_before_generic_exception_class(self):
        class FakeProgrammingError(Exception):
            pgcode = "42501"

        self.assertEqual(
            API._safe_database_error_code(FakeProgrammingError("do not expose")),
            "database_permission_error",
        )
        self.assertEqual(API._database_sqlstate(FakeProgrammingError()), "42501")

    def test_sqlstate_attribute_is_supported(self):
        class FakeDatabaseError(Exception):
            sqlstate = "42P01"

        self.assertEqual(
            API._safe_database_error_code(FakeDatabaseError()),
            "database_schema_error",
        )

    def test_invalid_sqlstate_is_ignored(self):
        class FakeDatabaseError(Exception):
            sqlstate = "not-a-code"
            pgcode = "bad"

        self.assertIsNone(API._database_sqlstate(FakeDatabaseError()))

    def test_database_failure_returns_safe_sqlstate_without_exception_text(self):
        class FakeProgrammingError(Exception):
            pgcode = "42501"

        class FailingStore:
            def __init__(self, database_url):
                pass

            def record_ci_event(self, event):
                raise FakeProgrammingError("sensitive connection detail")

        with patch.object(API, "PostgresCycleStore", FailingStore):
            status, result = send_request(self.payload())
        self.assertEqual(status, 503)
        self.assertEqual(result["diagnostic"], "database_permission_error")
        self.assertEqual(result["sqlstate"], "42501")
        self.assertNotIn("sensitive", json.dumps(result))

    def test_returns_503_when_database_is_not_configured(self):
        with patch.dict(os.environ, {"YJ64_DATABASE_URL": "", "DATABASE_URL": ""}):
            status, result = send_request(self.payload())
        self.assertEqual(status, 503)
        self.assertEqual(result["error"], "database_not_configured")


if __name__ == "__main__":
    unittest.main()
