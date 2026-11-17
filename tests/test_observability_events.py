import json
import unittest

from yj64_engineering_core.observability import (
    EVENT_SCHEMA,
    DiagnosticEvent,
    redact_sensitive_data,
)


class DiagnosticEventTests(unittest.TestCase):
    def make_event(self, **overrides):
        values = {
            "event_id": "evt-001",
            "event_name": "solver.completed",
            "severity": "info",
            "outcome": "succeeded",
            "service": "engineering-core",
            "component": "calculix-adapter",
            "environment": "test",
            "trace_id": "trace-001",
            "task_id": "task-001",
            "attributes": {"input_sha256": "a" * 64, "api_token": "do-not-store"},
        }
        values.update(overrides)
        return DiagnosticEvent(**values)

    def test_event_serializes_versioned_correlated_record(self):
        event = self.make_event()
        payload = json.loads(event.to_json())
        self.assertEqual(payload["schema"], EVENT_SCHEMA)
        self.assertEqual(payload["trace_id"], "trace-001")
        self.assertEqual(payload["task_id"], "task-001")
        self.assertEqual(payload["attributes"]["input_sha256"], "a" * 64)

    def test_sensitive_fields_are_redacted_before_serialization(self):
        event = self.make_event(attributes={
            "api_token": "top-secret",
            "nested": {"database_url": "postgres://user:password@host/db"},
            "message": "request used Bearer abc.def.ghi",
        })
        serialized = event.to_json()
        self.assertNotIn("top-secret", serialized)
        self.assertNotIn("user:password", serialized)
        self.assertNotIn("abc.def.ghi", serialized)
        payload = json.loads(serialized)
        self.assertEqual(payload["attributes"]["api_token"], "[REDACTED]")
        self.assertEqual(payload["attributes"]["nested"]["database_url"], "[REDACTED]")
        self.assertIn("Bearer [REDACTED]", payload["attributes"]["message"])

    def test_rejects_unknown_schema_and_invalid_sqlstate(self):
        with self.assertRaises(ValueError):
            self.make_event(schema="yj64.diagnostic.v99")
        with self.assertRaises(ValueError):
            self.make_event(sqlstate="bad")

    def test_rejects_naive_timestamp_and_invalid_outcome(self):
        with self.assertRaises(ValueError):
            self.make_event(timestamp="2026-11-17T12:00:00")
        with self.assertRaises(ValueError):
            self.make_event(outcome="maybe")

    def test_redaction_rejects_non_json_values(self):
        with self.assertRaises(TypeError):
            redact_sensitive_data({"bad": object()})


if __name__ == "__main__":
    unittest.main()
