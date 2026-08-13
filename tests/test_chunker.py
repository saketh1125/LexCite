import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingest.chunker import chunk_text

SAMPLE = "First paragraph.\n\nSecond paragraph with **clause** info.\n"


def test_paragraph_packing_and_ids():
    chunks = chunk_text(SAMPLE, "test.md")
    assert len(chunks) == 1
    assert chunks[0]["source_file"] == "test.md"
    assert chunks[0]["chunk_index"] == 0
    assert "First paragraph." in chunks[0]["text"]
    assert "Second paragraph" in chunks[0]["text"]


def test_deterministic_ids_and_crlf():
    a = chunk_text("x\r\n\r\ny", "f.md")
    b = chunk_text("x\n\ny", "f.md")
    assert [c["chunk_id"] for c in a] == [c["chunk_id"] for c in b]
    assert a[0]["chunk_id"] != chunk_text("x\n\ny", "g.md")[0]["chunk_id"]


def test_oversized_paragraph_split():
    raw = "word " * 500
    chunks = chunk_text(raw, "big.md")
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 810 for c in chunks)
    assert chunks[0]["text"] == raw[: len(chunks[0]["text"])]


def test_corpus_chunks_within_size():
    from src.ingest.loader import load_documents

    all_chunks = []
    for doc in load_documents():
        all_chunks.extend(chunk_text(doc["raw_text"], doc["source_file"]))
    assert len(all_chunks) >= 6
    assert all(len(c["text"]) <= 810 for c in all_chunks)
    ids = [c["chunk_id"] for c in all_chunks]
    assert len(ids) == len(set(ids))


def test_headings_stay_with_their_section():
    raw = (
        "# Lease excerpt — Unit 4B, Harbor View Tower (fiction)\n\n"
        "**Lessor:** Kiran Patel\n\n"
        "## Rent and deposit\n\n"
        "Monthly rent: **₹45,000**. Security deposit held: **₹1,35,000**.\n\n"
        "## Subletting\n\n"
        "Subletting is **not allowed**.\n"
    )
    chunks = chunk_text(raw, "lease.md")
    assert len(chunks) == 3
    assert "Unit 4B" in chunks[1]["text"] and "₹1,35,000" in chunks[1]["text"]
    assert "Unit 4B" in chunks[2]["text"] and "Subletting" in chunks[2]["text"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all chunker tests passed")