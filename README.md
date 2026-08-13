# LexCite — grounded Q&A over a legal corpus

A small Q&A HTTP API over a fixed corpus of legal-style documents. Built with
Python, FastAPI, LangGraph, and Pinecone. Every claim in an answer must cite a
retrieved chunk — the system refuses to guess.

## Features

- **Grounding-first RAG**: retrieval → grade → (rewrite/retry branch) →
  answer, as an explicit LangGraph state machine.
- **Citable answers**: `POST /ask` returns `answer`, `citations`
  (source file + chunk id + snippet), and a per-request `trace` of graph steps.
- **Code-enforced loop limit**: the graph rewrites its query at most
  `max_attempts` times — structurally incapable of infinite looping.
- **Idempotent ingestion**: deterministic chunk IDs (SHA-256 of
  `source_file::chunk_index`) make re-running the ingest script safe.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in Pinecone and NVIDIA NIM keys (one key covers chat + embeddings)
python scripts/ingest_cli.py
./run.sh                    # or: uvicorn src.api.server:app --reload
```

Or skip the manual steps: `./run.sh` creates the venv, installs requirements,
and starts the server for you (it warns but continues if `.env` is missing).

## Demo video

[Watch the demo (5–10 min)](PASTE_VIDEO_LINK_HERE) — install, ingest, start the
API, call `/ask` with curl, a few good answers with citations, one question the
docs cannot answer, and a walkthrough of the LangGraph layout
(`docs/langgraph.md`).

Then:

```bash
curl -s localhost:8000/health
curl -s localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the notice period in Priya Nambiar's agreement?"}'
```

## API

See `API_CONTRACT.md` for schemas. Summary:

- `POST /ask` `{"question": "..."}` → `{answer, citations[], trace[]}`
- `GET /health` → `{"status": "ok"}`
- `POST /ingest` → runs the same pipeline as `scripts/ingest_cli.py`

## Project layout

```
src/
  config.py              # every tunable, env-driven
  ingest/                # loader, chunker, embedder, pinecone client
  graph/                 # AgentState, nodes, LangGraph wiring
  api/server.py          # FastAPI app
scripts/ingest_cli.py    # one-shot ingestion
eval/test_cases.json     # evaluation questions + notes
docs/langgraph.md        # node inventory + diagram
```

## Pinecone checklist

- **Env vars** (in `.env.example`): `PINECONE_API_KEY`, `PINECONE_REGION`,
  `PINECONE_INDEX_NAME` (default `lexcite-index`), `PINECONE_NAMESPACE`
  (default `default`).
- **Index creation**: automatic — the first ingest run creates
  `lexcite-index` (serverless, cosine, dimension = `EMBEDDING_DIMENSION`).
  No manual console step needed. If an index with that name already exists but
  has a different dimension, the client fails loudly with an instruction
  rather than corrupting data.
- **Ingest twice?** Nothing changes: chunk IDs are deterministic
  (`sha256(source_file::chunk_index)`), so Pinecone `upsert` overwrites by ID.
  Verified: running the CLI twice back-to-back stays at 17 vectors (no
  duplicates). Use `--reset` (or `POST /ingest` equivalent) only when the
  corpus itself changed shape — it deletes the namespace first.
- **Verified with real Pinecone**: the ingest CLI reports the vector count
  fetched from Pinecone's own `describe_index_stats`, not a local counter
  (7 files → 17 chunks → 17 vectors).

## Design notes

- **Chunk size 800 / overlap 120 characters** (env-configurable): the corpus
  is clause-structured legal prose, so the chunker splits on blank lines into
  sections (heading + body), packs paragraphs within a section, and carries
  the document title into every chunk so facts stay attached to their context
  (a deposit figure is only meaningful alongside "Unit 4B, Harbor View
  Tower"). Oversized sections are hard-split at sentence boundaries with
  120 chars of overlap. Character-based rather than token-based sizing
  because the corpus and embeddings cost are small and the boundary logic is
  deterministic and idempotent. The section-packing was added after the eval
  showed whole-paragraph chunks left headings detached from their bodies.
- **Citations are built by code, not by the model**: the model lists which
  chunk numbers it used; code cross-references that list against the actually
  retrieved chunks. A model-fabricated chunk id is dropped and logged, never
  echoed back.
- **Grade parsing fails closed**: unparseable grade JSON is treated as `"bad"`,
  never `"good"`.
- The corpus (`gen_ai_takehome_sample_corpus/`) is the provided fictional
  sample — legal-style documents, all names and facts made up.

## What I skipped

- No auth/rate limiting on the API (local demo tool).
- No streaming responses.
- `POST /ingest` is optional convenience; the CLI is the primary path.