import unittest

from yj64_engineering_core.automation.payload_chunks import build_payload_manifest
from yj64_engineering_core.automation.postgres_store import PostgresCycleStore


class PayloadCursor:
    def __init__(self, manifest, chunks, acknowledgements=None, duplicate_manifest=False):
        self.manifest = manifest
        self.chunks = chunks
        self.acknowledgements = acknowledgements or []
        self.duplicate_manifest = duplicate_manifest
        self.one = None
        self.many = []
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))
        self.one = None
        self.many = []
        if "SELECT task_id FROM yj64_task_queue" in query:
            self.one = (12,)
        elif "INSERT INTO yj64_payload_manifests" in query:
            self.one = None if self.duplicate_manifest else (self.manifest["payload_id"],)
        elif "SELECT queue_task_id, total_sha256, manifest" in query:
            self.one = (12, self.manifest["total_sha256"], self.manifest)
        elif "SELECT manifest FROM yj64_payload_manifests" in query:
            self.one = (self.manifest,)
        elif "SELECT chunk_index, chunk_sha256, content" in query:
            chunk = next(c for c in self.chunks if c["chunk_id"] == params[1])
            self.one = (chunk["chunk_index"], chunk["chunk_sha256"], chunk["content"])
        elif "SELECT chunk_sha256 FROM yj64_payload_chunks" in query:
            chunk = next(c for c in self.chunks if c["chunk_id"] == params[1])
            self.one = (chunk["chunk_sha256"],)
        elif "INSERT INTO yj64_payload_chunk_acks" in query:
            self.one = (params[1],)
        elif "SELECT acknowledged_sha256 FROM yj64_payload_chunk_acks" in query:
            self.one = (params[2],)
        elif "SELECT chunk_id, content FROM yj64_payload_chunks" in query:
            self.many = [(c["chunk_id"], c["content"]) for c in self.chunks]
        elif "SELECT chunk_id FROM yj64_payload_chunk_acks" in query:
            self.many = [(chunk_id,) for chunk_id in self.acknowledgements]

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class PayloadConnection:
    def __init__(self, cursor):
        self.value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.value


class PayloadStoreTests(unittest.TestCase):
    def setup_payload(self, acknowledgements=None, duplicate_manifest=False):
        manifest, chunks = build_payload_manifest(
            "task-12", "payload-12", "alpha\nbeta\ngamma\n",
            token_counter=len, max_input_tokens=10, reserved_tokens=2,
        )
        cursor = PayloadCursor(
            manifest, chunks, acknowledgements=acknowledgements,
            duplicate_manifest=duplicate_manifest,
        )
        store = PostgresCycleStore("postgresql://test", lambda _: PayloadConnection(cursor))
        return store, cursor, manifest, chunks

    def test_persist_manifest_and_immutable_chunks_under_live_lease(self):
        store, cursor, manifest, chunks = self.setup_payload()
        result = store.save_payload_manifest(12, "worker-a", manifest, chunks)
        self.assertTrue(result["persisted"])
        self.assertEqual(result["payload_id"], "payload-12")
        self.assertTrue(any("INSERT INTO yj64_payload_chunks" in q for q, _ in cursor.statements))

    def test_duplicate_manifest_is_idempotent_when_content_matches(self):
        store, _, manifest, chunks = self.setup_payload(duplicate_manifest=True)
        result = store.save_payload_manifest(12, "worker-a", manifest, chunks)
        self.assertTrue(result["duplicate_manifest"])

    def test_acknowledgement_is_persisted_after_manifest_and_chunk_hash_check(self):
        store, cursor, manifest, chunks = self.setup_payload()
        chunk = chunks[0]
        result = store.acknowledge_payload_chunk("payload-12", {
            "payload_id": "payload-12",
            "chunk_index": chunk["chunk_index"],
            "chunk_id": chunk["chunk_id"],
            "chunk_sha256": chunk["chunk_sha256"],
        })
        self.assertTrue(result["verified"])
        self.assertTrue(any("INSERT INTO yj64_payload_chunk_acks" in q for q, _ in cursor.statements))

    def test_stateless_assembly_requires_complete_hash_verified_storage(self):
        store, _, manifest, chunks = self.setup_payload()
        result = store.assemble_payload_for_model(12, "worker-a", "payload-12")
        self.assertTrue(result["ready_for_model"])
        self.assertEqual(result["content"], "".join(c["content"] for c in chunks))
        self.assertEqual(result["total_sha256"], manifest["total_sha256"])

    def test_continuity_transport_cannot_finalize_before_all_acks(self):
        store, _, _, _ = self.setup_payload(acknowledgements=[])
        with self.assertRaisesRegex(RuntimeError, "every chunk is acknowledged"):
            store.assemble_payload_for_model(
                12, "worker-a", "payload-12", require_acknowledgements=True
            )

    def test_invalid_lease_duration_is_rejected(self):
        store, _, manifest, chunks = self.setup_payload()
        with self.assertRaises(ValueError):
            store.save_payload_manifest(12, "worker-a", manifest, chunks, lease_seconds=5)


if __name__ == "__main__":
    unittest.main()
