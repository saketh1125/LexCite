import hashlib
import re

from src.config import CHUNK_OVERLAP, CHUNK_SIZE


def _split_paragraph(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """Hard-split one oversized paragraph: sentence-ish boundaries, then chars."""
    pieces: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = start + size
        if end >= len(text):
            pieces.append((start, len(text)))
            break
        boundary = re.search(r"[.!?](\s)", text[start:end])
        cut = start + (boundary.end() if boundary else size)
        pieces.append((start, min(cut, len(text))))
        start = cut - overlap
    return pieces


def chunk_text(raw_text: str, source_file: str) -> list[dict]:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if len(block) <= CHUNK_SIZE:
            chunks.append(block)
            continue
        for s, e in _split_paragraph(block, CHUNK_SIZE, CHUNK_OVERLAP):
            chunk = block[s:e].strip()
            if chunk:
                chunks.append(chunk)

    out = []
    offset = 0
    for index, text in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{source_file}::{index}".encode()).hexdigest()[:16]
        char_start = offset
        char_end = offset + len(text)
        offset = char_end
        out.append({
            "chunk_id": chunk_id,
            "source_file": source_file,
            "chunk_index": index,
            "text": text,
            "char_start": char_start,
            "char_end": char_end,
        })
    return out