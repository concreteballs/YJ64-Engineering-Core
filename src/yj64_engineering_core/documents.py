"""Immutable intake and structural segmentation for engineering documents.

The first adapter deliberately supports UTF-8 Markdown and plain text only.
PDF/DOCX/OCR extraction and translation are separate replaceable services.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Literal


_SEGMENT_KINDS = {"heading", "paragraph", "table", "code"}
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_SUPPORTED_SUFFIXES = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain"}


@dataclass(frozen=True, slots=True)
class DocumentSegment:
    """A source-text block linked to exact character and line offsets."""
    segment_id: str
    kind: Literal["heading", "paragraph", "table", "code"]
    text: str
    char_start: int
    char_end: int
    line_start: int
    line_end: int

    def __post_init__(self) -> None:
        if not self.segment_id or self.kind not in _SEGMENT_KINDS:
            raise ValueError("segment id and supported kind are required")
        if not self.text.strip():
            raise ValueError("document segments cannot be empty")
        if self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("invalid character span")
        if self.line_start < 1 or self.line_end < self.line_start:
            raise ValueError("invalid line span")


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Immutable source artifact plus a navigable text extraction.

    raw_bytes are retained exactly as imported; extracted text and segments are
    derived views and never replace the source artifact.
    """
    document_id: str
    filename: str
    media_type: str
    sha256: str
    byte_length: int
    source_language: str | None
    text: str
    segments: tuple[DocumentSegment, ...]
    raw_bytes: bytes

    def __post_init__(self) -> None:
        if not self.document_id or not self.filename or not self.media_type:
            raise ValueError("document identity and media type are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if self.byte_length != len(self.raw_bytes):
            raise ValueError("byte_length does not match retained source bytes")
        if hashlib.sha256(self.raw_bytes).hexdigest() != self.sha256:
            raise ValueError("source bytes do not match sha256")
        if not isinstance(self.segments, tuple) or not all(
            isinstance(item, DocumentSegment) for item in self.segments
        ):
            raise TypeError("segments must be a tuple of DocumentSegment values")

    def metadata_json(self) -> str:
        """Serialize metadata and segment map without duplicating source bytes/text."""
        payload = {
            "document_id": self.document_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "source_language": self.source_language,
            # Keep the navigable span map, not extracted source text. The full
            # text remains available on the document object/source artifact.
            "segments": [
                {
                    key: value
                    for key, value in asdict(item).items()
                    if key != "text"
                }
                for item in self.segments
            ],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _classify_block(lines: list[str], in_fence: bool) -> str:
    if in_fence:
        return "code"
    if lines[0].lstrip().startswith("#"):
        return "heading"
    if any("|" in line for line in lines) and any(
        re.match(r"^\s*\|?\s*:?-{3,}", line) for line in lines
    ):
        return "table"
    return "paragraph"


def _segment_text(text: str, digest: str) -> tuple[DocumentSegment, ...]:
    lines = text.splitlines(keepends=True)
    segments: list[DocumentSegment] = []
    block_lines: list[str] = []
    block_start = 0
    char_offset = 0
    line_number = 1
    fence_open = False

    def flush(end_offset: int, end_line: int) -> None:
        nonlocal block_lines, block_start
        if not block_lines:
            return
        body = "".join(block_lines).rstrip("\r\n")
        if body.strip():
            kind = _classify_block(block_lines, fence_open or any(
                line.lstrip().startswith(("\u0060\u0060\u0060", "~~~")) for line in block_lines
            ))
            start = block_start
            end = start + len(body)
            identity = hashlib.sha256(
                f"{digest}:{start}:{end}:{kind}".encode("utf-8")
            ).hexdigest()[:20]
            segments.append(DocumentSegment(
                segment_id=f"seg-{identity}", kind=kind, text=body,
                char_start=start, char_end=end,
                line_start=line_number - len(block_lines),
                line_end=end_line,
            ))
        block_lines = []

    for line in lines:
        if not line.strip():
            flush(char_offset, line_number - 1)
        else:
            if not block_lines:
                block_start = char_offset
            block_lines.append(line)
            if line.lstrip().startswith(("\u0060\u0060\u0060", "~~~")):
                fence_open = not fence_open
        char_offset += len(line)
        line_number += 1
    flush(char_offset, line_number - 1)
    return tuple(segments)


def ingest_document(
    data: bytes,
    filename: str,
    source_language: str | None = None,
) -> SourceDocument:
    """Import UTF-8 Markdown/plain text without altering the original bytes."""
    if not isinstance(data, bytes):
        raise TypeError("document data must be bytes")
    if not data:
        raise ValueError("document is empty")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string")
    safe_name = Path(filename).name
    media_type = _SUPPORTED_SUFFIXES.get(Path(safe_name).suffix.lower())
    if media_type is None:
        raise ValueError("supported document formats are UTF-8 .md, .markdown and .txt")
    if source_language is not None and not _LANGUAGE_TAG.fullmatch(source_language):
        raise ValueError("source_language must be a valid BCP 47-style language tag")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("document must be valid UTF-8 text") from exc
    if not text.strip():
        raise ValueError("document contains no readable text")
    digest = hashlib.sha256(data).hexdigest()
    segments = _segment_text(text, digest)
    return SourceDocument(
        document_id=f"doc-{digest[:20]}",
        filename=safe_name,
        media_type=media_type,
        sha256=digest,
        byte_length=len(data),
        source_language=source_language,
        text=text,
        segments=segments,
        raw_bytes=data,
    )
