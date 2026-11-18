import json
import unittest

from yj64_engineering_core.automation.postgres_store import PostgresCycleStore
from yj64_engineering_core.automation.task_requests import (
    PARENT_TASK_QUEUE_TYPE,
    enqueue_task_request,
)
from yj64_engineering_core.task_contracts import TaskRequest


class RecordingQueueStore:
    def __init__(self):
        self.calls = []

    def enqueue_task(self, task_type, payload, dedupe_key, *, max_attempts=3):
        self.calls.append((task_type, payload, dedupe_key, max_attempts))
        return {"enqueued": True, "duplicate": False, "task_id": 41, "state": "pending"}




class QueueCursor:
    def __init__(self, *, existing=None):
        self.existing = existing
        self.statements = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.statements.append((query, params))
        if "INSERT INTO yj64_task_queue" in query:
            self.row = (41,) if self.existing is None else None
        elif "SELECT task_id, task_type, payload, state" in query:
            self.row = self.existing

    def fetchone(self):
        return self.row


class QueueConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_value


class TaskRequestQueueTests(unittest.TestCase):
    def make_request(self, objective="Inspect the repository"):
        return TaskRequest(
            task_id="repo-review-001",
            task_type="code.review",
            title="Repository review",
            objective=objective,
            input_data={"repository": "owner/project", "ref": "main"},
            constraints={"read_only": True},
            requested_capabilities=("github.read", "python.test"),
        )

    def test_enqueues_generic_envelope_in_existing_queue(self):
        store = RecordingQueueStore()
        result = enqueue_task_request(store, self.make_request(), max_attempts=5)

        self.assertEqual(result["task_id"], 41)
        self.assertEqual(len(store.calls), 1)
        task_type, payload, dedupe_key, max_attempts = store.calls[0]
        self.assertEqual(task_type, PARENT_TASK_QUEUE_TYPE)
        self.assertEqual(payload, {"task_request": self.make_request().to_dict()})
        self.assertEqual(dedupe_key, "task-request:repo-review-001")
        self.assertEqual(max_attempts, 5)

    def test_same_task_id_keeps_same_idempotency_key(self):
        first_store = RecordingQueueStore()
        second_store = RecordingQueueStore()
        enqueue_task_request(first_store, self.make_request("First objective"))
        enqueue_task_request(second_store, self.make_request("Changed objective"))

        self.assertEqual(first_store.calls[0][2], second_store.calls[0][2])
        self.assertNotEqual(first_store.calls[0][1], second_store.calls[0][1])

    def test_rejects_non_task_request(self):
        with self.assertRaises(TypeError):
            enqueue_task_request(RecordingQueueStore(), {"task_id": "not-a-contract"})

    def test_postgres_store_accepts_parent_task_type_and_inserts_json_payload(self):
        cursor = QueueCursor()
        store = PostgresCycleStore(
            "postgresql://test",
            lambda _: QueueConnection(cursor),
        )
        result = enqueue_task_request(store, self.make_request())

        self.assertTrue(result["enqueued"])
        self.assertEqual(result["task_id"], 41)
        query, params = cursor.statements[0]
        self.assertIn("INSERT INTO yj64_task_queue", query)
        self.assertEqual(params[0], PARENT_TASK_QUEUE_TYPE)
        self.assertEqual(
            json.loads(params[1]),
            json.loads(json.dumps({"task_request": self.make_request().to_dict()})),
        )
        self.assertEqual(params[2], "task-request:repo-review-001")

    def test_postgres_store_accepts_exact_duplicate_but_rejects_conflicting_payload(self):
        original = self.make_request()
        original_payload = json.loads(json.dumps({"task_request": original.to_dict()}))
        existing = (41, PARENT_TASK_QUEUE_TYPE, original_payload, "pending")
        cursor = QueueCursor(existing=existing)
        store = PostgresCycleStore(
            "postgresql://test",
            lambda _: QueueConnection(cursor),
        )

        duplicate = enqueue_task_request(store, original)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["task_id"], 41)

        with self.assertRaisesRegex(ValueError, "conflicting task content"):
            enqueue_task_request(store, self.make_request("Different objective"))

    def test_rejects_store_without_queue_interface(self):
        with self.assertRaises(TypeError):
            enqueue_task_request(object(), self.make_request())


if __name__ == "__main__":
    unittest.main()
