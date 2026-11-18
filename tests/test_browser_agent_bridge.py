import unittest
from datetime import datetime, timezone, timedelta

from yj64_engineering_core.automation.browser_agent_bridge import (
    EXPECTED_BRANCH, EXPECTED_REPOSITORY, SCHEMA_VERSION, create_envelope, payload_hash, validate_envelope,
)


class BrowserAgentEnvelopeTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        self.now = now
        payload = {"conclusion": "success", "safe_summary": "tests passed"}
        self.message = {
            "schema_version": SCHEMA_VERSION,
            "message_id": "msg-00000001",
            "message_type": "ci_observation",
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "repository": EXPECTED_REPOSITORY,
            "branch": EXPECTED_BRANCH,
            "task_id": 4,
            "idempotency_key": "dedupe-msg-00001",
            "run_id": 12,
            "run_attempt": 1,
            "commit_sha": "a" * 40,
            "payload_sha256": payload_hash(payload),
            "payload": payload,
        }

    def test_accepts_valid_message_and_normalizes_timestamps(self):
        valid = validate_envelope(self.message, now=self.now)
        self.assertEqual(valid["schema_version"], SCHEMA_VERSION)
        self.assertTrue(valid["created_at"].endswith("Z"))

    def test_create_envelope_builds_valid_council_message(self):
        envelope = create_envelope(
            message_type="council_request",
            task_id=91,
            idempotency_key="council-idem-12345",
            payload={"mode": "consensus", "title": "Review", "prompt": "Check this change."},
            now=self.now,
        )
        self.assertEqual(envelope["message_type"], "council_request")
        self.assertEqual(envelope["task_id"], 91)
        self.assertEqual(validate_envelope(envelope, now=self.now)["payload"]["mode"], "consensus")

    def test_stable_message_id_supports_idempotent_envelope_replay(self):
        kwargs = {
            "message_type": "council_result",
            "task_id": 91,
            "idempotency_key": "council-result-12345",
            "payload": {"request_id": "request-123", "execution_status": "completed"},
            "now": self.now,
            "message_id": "stable-result-message-123456",
            "ttl_seconds": 2592000,
        }
        first = create_envelope(**kwargs)
        second = create_envelope(**kwargs)
        self.assertEqual(first, second)

    def test_rejects_wrong_repository_or_branch(self):
        bad = dict(self.message, repository="someone/else")
        with self.assertRaisesRegex(ValueError, "scope"):
            validate_envelope(bad, now=self.now)
        bad = dict(self.message, branch="feature")
        with self.assertRaisesRegex(ValueError, "scope"):
            validate_envelope(bad, now=self.now)

    def test_rejects_expired_and_naive_timestamps(self):
        bad = dict(self.message, created_at=(self.now - timedelta(hours=2)).isoformat(), expires_at=(self.now - timedelta(hours=1)).isoformat())
        with self.assertRaisesRegex(ValueError, "expired"):
            validate_envelope(bad, now=self.now)
        bad = dict(self.message, created_at=self.now.replace(tzinfo=None).isoformat())
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_envelope(bad, now=self.now)

    def test_rejects_payload_tampering_and_non_json(self):
        bad = dict(self.message, payload={"conclusion": "failure"})
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_envelope(bad, now=self.now)
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            payload_hash({"not_json": object()})

    def test_rejects_unknown_envelope_keys(self):
        bad = dict(self.message, injected_extra="unexpected")
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            validate_envelope(bad, now=self.now)

    def test_rejects_invalid_run_identity_and_schema(self):
        bad = dict(self.message, run_attempt=0)
        with self.assertRaisesRegex(ValueError, "run_attempt"):
            validate_envelope(bad, now=self.now)
        bad = dict(self.message, schema_version="v99")
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_envelope(bad, now=self.now)


if __name__ == "__main__":
    unittest.main()
