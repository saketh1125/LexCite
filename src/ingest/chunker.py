import hashlib
import re

from src.config import CHUNK_OVERLAP, CHUNK_SIZE


def _split_paragraph(text: str, size: int, overlap: int) -> list[str]:
    """Hard-split one oversized section: sentence-ish boundaries, then chars."""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        if end >= len(text):
            pieces.append(text[start:])
            break
        boundary = re.search(r"[.!?](\s)", text[start:end])
        cut = start + (boundary.end() if boundary else size)
        pieces.append(text[start:cut])
        start = cut - overlap
    return pieces


def chunk_text(raw_text: str, source_file: str) -> list[dict]:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        return []

    title = blocks[0]
    sections: list[str] = []
    current = []
    for block in blocks:
        if block.startswith("#") and current:
            sections.append("\n\n".join(current))
            current = [block]
        else:
            current.append(block)
    if current:
        sections.append("\n\n".join(current))

    chunks: list[str] = []
    for section in sections:
        if len(section) > CHUNK_SIZE:
            chunks.extend(_split_paragraph(section, CHUNK_SIZE, CHUNK_OVERLAP))
        elif section.startswith(title):
            chunks.append(section)
        else:
            chunks.append(f"{title}\n\n{section}")

    out = []
    offset = 0
    for index, chunk in enumerate(chunks):
        chunk_id = hashlib.sha256(f"{source_file}::{index}".encode()).hexdigest()[:16]
        char_start = offset
        char_end = offset + len(chunk)
        offset = char_end
        out.append({
            "chunk_id": chunk_id,
            "source_file": source_file,
            "chunk_index": index,
            "text": chunk,
            "char_start": char_start,
            "char_end": char_end,
        })
    return out