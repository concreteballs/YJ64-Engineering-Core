"""Deterministic chunk manifests and integrity-checked payload assembly.

The module is provider-neutral. It does not assume that independent model API
calls share context; callers must assemble the full payload before stateless calls.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Callable, Mapping


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _split_oversized_line(line: str, budget: int, token_counter: Callable[[str], int]) -> list[str]:
    parts: list[str] = []
    remaining = line
    while remaining:
        low, high = 1, len(remaining)
        best = 0
        while low <= high:
            middle = (low + high) // 2
            if token_counter(remaining[:middle]) <= budget:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == 0:
            raise ValueError("one character exceeds the available token budget")
        parts.append(remaining[:best])
        remaining = remaining[best:]
    return parts


def build_payload_manifest(
    task_id: str,
    payload_id: str,
    content: str,
    *,
    token_counter: Callable[[str], int],
    max_input_tokens: int,
    reserved_tokens: int = 1024,
    max_chunks: int = 256,
    encoding: str = "utf-8",
    source_refs: list[str] | None = None,
) -> tuple[dict, list[dict]]:
    """Split exact source text below a conservative input-token budget.

    Newlines and all other source characters are preserved. The splitter prefers
    line/paragraph boundaries and only splits within a line when necessary.
    """
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id is required")
    if not isinstance(payload_id, str) or not payload_id.strip():
        raise ValueError("payload_id is required")
    if not isinstance(content, str) or not content:
        raise ValueError("content must be a non-empty string")
    if not callable(token_counter):
        raise ValueError("token_counter must be callable")
    if not isinstance(max_input_tokens, int) or isinstance(max_input_tokens, bool) or max_input_tokens < 1:
        raise ValueError("max_input_tokens must be a positive integer")
    if not isinstance(reserved_tokens, int) or isinstance(reserved_tokens, bool) or reserved_tokens < 0:
        raise ValueError("reserved_tokens must be a non-negative integer")
    if reserved_tokens >= max_input_tokens:
        raise ValueError("reserved_tokens must be smaller than max_input_tokens")
    if not isinstance(max_chunks, int) or isinstance(max_chunks, bool) or max_chunks < 1:
        raise ValueError("max_chunks must be a positive integer")
    budget = max_input_tokens - reserved_tokens

    units: list[str] = []
    for line in content.splitlines(keepends=True):
        if token_counter(line) <= budget:
            units.append(line)
        else:
            units.extend(_split_oversized_line(line, budget, token_counter))

    chunks_text: list[str] = []
    current = ""
    for unit in units:
        candidate = current + unit
        if current and token_counter(candidate) > budget:
            chunks_text.append(current)
            current = unit
        else:
            current = candidate
        if token_counter(current) > budget:
            raise ValueError("chunk exceeds token budget after splitting")
    if current:
        chunks_text.append(current)
    if len(chunks_text) > max_chunks:
        raise ValueError("payload exceeds max_chunks; decompose the task")

    chunks: list[dict] = []
    manifest_chunks: list[dict] = []
    for index, chunk_text in enumerate(chunks_text, start=1):
        chunk_hash = _digest(chunk_text)
        chunk_id = sha256(
            f"{payload_id}:{index}:{chunk_hash}".encode("utf-8")
        ).hexdigest()
        chunks.append({
            "chunk_id": chunk_id,
            "chunk_index": index,
            "content": chunk_text,
            "chunk_sha256": chunk_hash,
            "estimated_tokens": token_counter(chunk_text),
        })
        manifest_chunks.append({
            "chunk_id": chunk_id,
            "chunk_index": index,
            "chunk_sha256": chunk_hash,
            "estimated_tokens": token_counter(chunk_text),
            "character_count": len(chunk_text),
        })

    manifest = {
        "protocol_version": 1,
        "task_id": task_id,
        "payload_id": payload_id,
        "total_chunks": len(chunks),
        "total_sha256": _digest(content),
        "encoding": encoding,
        "max_input_tokens": max_input_tokens,
        "reserved_tokens": reserved_tokens,
        "chunk_budget_tokens": budget,
        "source_refs": list(source_refs or []),
        "chunks": manifest_chunks,
    }
    return manifest, chunks


def validate_chunk_ack(manifest: dict, acknowledgement: dict) -> dict:
    """Validate and normalize a provider/transport acknowledgement."""
    if not isinstance(manifest, dict) or not isinstance(acknowledgement, dict):
        raise ValueError("manifest and acknowledgement must be objects")
    payload_id = acknowledgement.get("payload_id")
    index = acknowledgement.get("chunk_index")
    if payload_id != manifest.get("payload_id"):
        raise ValueError("acknowledgement payload_id mismatch")
    if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= manifest.get("total_chunks", 0):
        raise ValueError("acknowledgement chunk_index is invalid")
    expected = manifest["chunks"][index - 1]
    if acknowledgement.get("chunk_id") != expected["chunk_id"]:
        raise ValueError("acknowledgement chunk_id mismatch")
    if acknowledgement.get("chunk_sha256") != expected["chunk_sha256"]:
        raise ValueError("acknowledgement chunk hash mismatch")
    return {
        "payload_id": payload_id,
        "chunk_index": index,
        "chunk_id": expected["chunk_id"],
        "chunk_sha256": expected["chunk_sha256"],
        "verified": True,
    }


def assemble_payload(manifest: dict, chunks_by_id: Mapping[str, str]) -> str:
    """Return the canonical full payload only after every hash is verified."""
    if not isinstance(manifest, dict) or not isinstance(chunks_by_id, Mapping):
        raise ValueError("manifest and chunks_by_id are required")
    entries = manifest.get("chunks")
    total = manifest.get("total_chunks")
    if not isinstance(entries, list) or not isinstance(total, int) or total != len(entries) or total < 1:
        raise ValueError("manifest chunk count is invalid")
    if len(chunks_by_id) != total:
        raise ValueError("payload is incomplete or contains unexpected chunks")

    ordered: list[str] = []
    for expected_index, entry in enumerate(entries, start=1):
        if entry.get("chunk_index") != expected_index:
            raise ValueError("manifest chunk order is invalid")
        chunk_id = entry.get("chunk_id")
        if chunk_id not in chunks_by_id:
            raise ValueError("payload is missing a chunk")
        text = chunks_by_id[chunk_id]
        if not isinstance(text, str) or _digest(text) != entry.get("chunk_sha256"):
            raise ValueError("chunk content hash mismatch")
        if len(text) != entry.get("character_count"):
            raise ValueError("chunk character count mismatch")
        ordered.append(text)

    assembled = "".join(ordered)
    if _digest(assembled) != manifest.get("total_sha256"):
        raise ValueError("total payload hash mismatch")
    return assembled


def finalize_envelope(manifest: dict) -> str:
    """Create the explicit FINALIZE marker; caller must assemble/verify first."""
    if not isinstance(manifest, dict) or not manifest.get("payload_id"):
        raise ValueError("valid manifest is required")
    return (
        "YJ64 CHUNKED INPUT — FINALIZE\n"
        f"task_id: {manifest['task_id']}\n"
        f"payload_id: {manifest['payload_id']}\n"
        f"chunk_count: {manifest['total_chunks']}\n"
        f"total_payload_sha256: {manifest['total_sha256']}\n"
        "Begin work only after the orchestrator confirms every chunk and the "
        "reassembled payload hash."
    )
