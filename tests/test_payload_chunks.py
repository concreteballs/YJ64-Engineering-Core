import unittest

from yj64_engineering_core.automation.payload_chunks import (
    assemble_payload,
    build_payload_manifest,
    finalize_envelope,
    validate_chunk_ack,
)


class PayloadChunkTests(unittest.TestCase):
    def build(self, content):
        return build_payload_manifest(
            "task-1", "payload-1", content,
            token_counter=len, max_input_tokens=12, reserved_tokens=2,
        )

    def test_split_preserves_exact_text_and_respects_budget(self):
        source = "alpha\nbeta-gamma-delta\nomega\n"
        manifest, chunks = self.build(source)
        self.assertGreater(manifest["total_chunks"], 1)
        self.assertEqual("".join(chunk["content"] for chunk in chunks), source)
        self.assertTrue(all(chunk["estimated_tokens"] <= 10 for chunk in chunks))
        assembled = assemble_payload(
            manifest, {chunk["chunk_id"]: chunk["content"] for chunk in chunks}
        )
        self.assertEqual(assembled, source)

    def test_long_single_line_is_split_without_loss(self):
        source = "abcdefghijklmnopqrstuv"
        manifest, chunks = self.build(source)
        self.assertEqual("".join(c["content"] for c in chunks), source)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c["estimated_tokens"] <= 10 for c in chunks))

    def test_manifest_and_chunk_ids_are_deterministic(self):
        first, first_chunks = self.build("same input\n")
        second, second_chunks = self.build("same input\n")
        self.assertEqual(first, second)
        self.assertEqual(first_chunks, second_chunks)

    def test_acknowledgement_is_bound_to_payload_index_and_hash(self):
        manifest, chunks = self.build("alpha\nbeta\n")
        chunk = chunks[0]
        ack = {
            "payload_id": manifest["payload_id"],
            "chunk_index": chunk["chunk_index"],
            "chunk_id": chunk["chunk_id"],
            "chunk_sha256": chunk["chunk_sha256"],
        }
        self.assertTrue(validate_chunk_ack(manifest, ack)["verified"])
        ack["chunk_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_chunk_ack(manifest, ack)

    def test_incomplete_or_corrupt_assembly_is_rejected(self):
        manifest, chunks = self.build("alpha\nbeta\n")
        incomplete = {chunks[0]["chunk_id"]: chunks[0]["content"]}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            assemble_payload(manifest, incomplete)
        corrupt = {c["chunk_id"]: c["content"] for c in chunks}
        corrupt[chunks[0]["chunk_id"]] += "tampered"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            assemble_payload(manifest, corrupt)

    def test_finalize_marker_contains_total_integrity_hash(self):
        manifest, _ = self.build("payload")
        envelope = finalize_envelope(manifest)
        self.assertIn("FINALIZE", envelope)
        self.assertIn(manifest["total_sha256"], envelope)
        self.assertIn(manifest["payload_id"], envelope)

    def test_invalid_budget_and_chunk_limit_are_rejected(self):
        with self.assertRaises(ValueError):
            build_payload_manifest(
                "t", "p", "x", token_counter=len,
                max_input_tokens=10, reserved_tokens=10,
            )
        with self.assertRaisesRegex(ValueError, "max_chunks"):
            build_payload_manifest(
                "t", "p", "abcdefghijklmno", token_counter=len,
                max_input_tokens=10, reserved_tokens=2, max_chunks=1,
            )


if __name__ == "__main__":
    unittest.main()
