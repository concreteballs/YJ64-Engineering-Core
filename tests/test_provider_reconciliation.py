import unittest
from decimal import Decimal

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class ReconciliationCursor:
    def __init__(self, *, unknown_count=0):
        self.unknown_count = unknown_count
        self.one = None
        self.many = []
        self.rowcount = 1
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        self.one = None
        self.many = []
        self.rowcount = 1
        if "RETURNING task.task_id" in query:
            self.one = (9, "process_ci_event", {"event_id": 2}, 1, 3, None)
        elif "SELECT task_id FROM yj64_task_queue" in query:
            self.one = (9,)
        elif "SELECT input_tokens_estimated, output_tokens_estimated" in query:
            self.one = (100, 40, Decimal("0.02"), True, "unknown")
        elif "SELECT count(*) FROM yj64_provider_request_reservations" in query:
            self.one = (self.unknown_count,)
        elif "SELECT reservation_id, idempotency_key, provider, model" in query:
            self.many = [(
                "r-1", "idem-1", "provider-a", "model-a", "/v1",
                "a" * 64, "req-1", None, 100, 40, "transient_transport_error",
            )]

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class ReconciliationConnection:
    def __init__(self, cursor):
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.value


class ProviderReconciliationTests(unittest.TestCase):
    def store(self, cursor):
        return PostgresCycleStore(
            "postgresql://test", lambda _: ReconciliationConnection(cursor)
        )

    def test_reconciliation_claim_does_not_consume_execution_attempt(self):
        cursor = ReconciliationCursor()
        task = self.store(cursor).claim_next_reconciliation_task("worker-a")
        self.assertTrue(task["reconciliation_only"])
        self.assertEqual(task["task_id"], 9)
        query = next(q for q, _ in cursor.statements if "UPDATE yj64_task_queue" in q)
        self.assertNotIn("attempts = attempts + 1", query)
        self.assertIn("FOR UPDATE SKIP LOCKED", query)

    def test_unknown_request_listing_exposes_idempotency_and_hash_not_prompt(self):
        cursor = ReconciliationCursor()
        rows = self.store(cursor).list_unknown_provider_requests(9, "worker-a")
        self.assertEqual(rows[0]["idempotency_key"], "idem-1")
        self.assertEqual(rows[0]["payload_sha256"], "a" * 64)
        self.assertNotIn("prompt", rows[0])

    def test_authoritative_not_found_releases_budget_and_resumes_task(self):
        cursor = ReconciliationCursor(unknown_count=0)
        result = self.store(cursor).resolve_unknown_provider_request(
            9, "worker-a", "r-1", outcome="provider_not_found",
            evidence_ref="provider-lookup-event-91",
        )
        self.assertEqual(result["reservation_state"], "failed")
        self.assertTrue(result["task_resumed"])
        update = next(q for q, _ in cursor.statements
                      if "UPDATE yj64_provider_request_reservations" in q)
        self.assertIn("resolution_evidence_ref", update)
        queue_updates = [q for q, _ in cursor.statements if "UPDATE yj64_task_queue" in q]
        self.assertTrue(any("state = 'pending'" in q for q in queue_updates))

    def test_provider_found_requires_retrievable_result_artifact(self):
        with self.assertRaisesRegex(ValueError, "provider_result_ref"):
            self.store(ReconciliationCursor()).resolve_unknown_provider_request(
                9, "worker-a", "r-1", outcome="provider_found",
                evidence_ref="provider-lookup-event-92",
            )

    def test_provider_found_persists_artifact_reference(self):
        cursor = ReconciliationCursor(unknown_count=0)
        result = self.store(cursor).resolve_unknown_provider_request(
            9, "worker-a", "r-1", outcome="provider_found",
            evidence_ref="provider-lookup-event-93",
            provider_result_ref="artifact://model-results/response-93",
        )
        self.assertEqual(result["reservation_state"], "completed")
        self.assertEqual(result["provider_result_ref"], "artifact://model-results/response-93")
        update_params = next(params for query, params in cursor.statements
                             if "UPDATE yj64_provider_request_reservations" in query)
        self.assertEqual(update_params[7], "artifact://model-results/response-93")

    def test_signed_urls_are_not_accepted_as_reconciliation_references(self):
        with self.assertRaisesRegex(ValueError, "signed URL"):
            self.store(ReconciliationCursor()).resolve_unknown_provider_request(
                9, "worker-a", "r-1", outcome="provider_not_found",
                evidence_ref="https://example.test/check?token=secret",
            )


if __name__ == "__main__":
    unittest.main()
