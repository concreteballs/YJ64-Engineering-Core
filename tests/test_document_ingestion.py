import hashlib
import unittest

from yj64_engineering_core.documents import ingest_document


class DocumentIngestionTests(unittest.TestCase):
    def test_markdown_import_preserves_original_and_maps_segments(self):
        raw = (
            "# Pump specification\n\n"
            "Pressure rating: 150 psi.\n"
            "Nominal size: NPS 2.\n\n"
            "| Item | Value |\n| --- | --- |\n| Bore | 2 in |\n\n"
            "```python\nprint('do not translate')\n```\n"
        ).encode("utf-8")
        document = ingest_document(raw, "manual.md", source_language="en-US")
        self.assertEqual(document.raw_bytes, raw)
        self.assertEqual(document.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(document.byte_length, len(raw))
        self.assertEqual(document.source_language, "en-US")
        self.assertEqual(document.segments[0].kind, "heading")
        self.assertEqual(document.segments[1].kind, "paragraph")
        self.assertEqual(document.segments[2].kind, "table")
        self.assertEqual(document.segments[3].kind, "code")
        for segment in document.segments:
            self.assertEqual(
                document.text[segment.char_start:segment.char_end], segment.text
            )

    def test_plain_text_import_and_stable_identity(self):
        raw = "First paragraph.\n\nSecond paragraph.".encode()
        first = ingest_document(raw, "notes.txt")
        second = ingest_document(raw, "notes.txt")
        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(
            [item.segment_id for item in first.segments],
            [item.segment_id for item in second.segments],
        )
        self.assertEqual(first.media_type, "text/plain")

    def test_metadata_json_excludes_source_payload(self):
        document = ingest_document(b"Keep source unchanged.", "note.txt")
        metadata = document.metadata_json()
        self.assertIn(document.sha256, metadata)
        self.assertNotIn("Keep source unchanged.", metadata)
        self.assertNotIn("raw_bytes", metadata)

    def test_unsupported_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported document formats"):
            ingest_document(b"%PDF-1.7", "manual.pdf")

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            ingest_document(b"\xff\xfe", "note.txt")

    def test_empty_document_and_invalid_language_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            ingest_document(b"", "note.md")
        with self.assertRaisesRegex(ValueError, "BCP 47"):
            ingest_document(b"hello", "note.md", source_language="not a locale")


if __name__ == "__main__":
    unittest.main()
