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
cp .env.example .env        # fill in Pinecone, embedding, and NVIDIA NIM keys
python scripts/ingest_cli.py
uvicorn src.api.server:app --reload
```

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

## Design notes

- **Chunk size 800 / overlap 120 characters** (env-configurable): the corpus
  is clause-structured legal prose, and paragraphs tend to be 100–300 chars,
  so a paragraph-packing chunker keeps whole clauses together while 800 chars
  leaves room for multi-clause sections; the 120-char overlap (≈15%) covers
  sentences that straddle a boundary. Character-based rather than
  token-based sizing because the corpus and embeddings cost are small and the
  boundary logic is deterministic and idempotent.
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