# LexCite — grounded Q&A over a legal corpus

A small Q&A HTTP API over a fixed corpus of legal-style documents — Python,
FastAPI, **LangGraph**, and **Pinecone**. Every claim in an answer must cite a
retrieved chunk; the system refuses to guess.

**Repository:** https://github.com/saketh1125/LexCite.git



---

## The LangGraph flow (the core of the system)

Every `/ask` request runs this graph (`src/graph/build_graph.py`). Reviewers:
this is the piece the scoring rubric looks at.

```
START
  │
  ▼
retrieve ───────────────► grade_chunks
  ▲                             │
  │        (grade == "bad"      │ (grade == "good")
  │         and attempt <       ▼
  │         max_attempts)  generate_answer ───► END
  │                             │
  │                             │ (grade == "bad", attempts exhausted)
  └──────── rewrite_query       ▼
         ┌──────────────── cannot_answer ───► END
         └──► retrieve (loop back)
```

| Node | What it does | Sets in state |
|---|---|---|
| `retrieve` | Embeds the search query (NVIDIA NIM), queries Pinecone (`top_k=6`), stores matches | `retrieved_chunks`, `trace` |
| `grade_chunks` | Separate LLM call judges whether the chunks can answer the question. Strict JSON `{"grade": "good"\|"bad", "reason"}`; **unparseable output fails closed to "bad"**. Empty retrieval → "bad" without an LLM call | `grade`, `grade_reason`, `trace` |
| `rewrite_query` | LLM reformulates the query, increments `attempt` (the only place the counter changes), loops back to `retrieve` | `search_query`, `attempt`, `trace` |
| `generate_answer` | LLM answers from chunks only and ends with a `CITED: n, m` line; **code** builds the citation list by cross-referencing against `retrieved_chunks` — model-fabricated ids are dropped and logged, never echoed | `answer`, `citations`, `trace` |
| `cannot_answer` | Deterministic, no LLM: fixed refusal + empty citations | `answer`, `citations`, `trace` |

**Loop safety — by construction, not by prompt:** `route_after_grade` is the
only way flow leaves `grade_chunks`; `rewrite_query` always routes back to
`retrieve`. The maximum number of retrieval passes per request is therefore
`max_attempts + 1` (state counter, default 2). A `recursion_limit` is set at
invocation as a second, independent safety net.

Full detail, prompts, and wiring: `docs/langgraph.md`, `PROMPTS.md`.

---

## Features

- **Grounding-first RAG**: retrieval → grade → (rewrite/retry branch) →
  answer, as an explicit LangGraph state machine (diagram above).
- **Citable answers**: `POST /ask` returns `answer`, `citations`
  (source file + chunk id + snippet), and a per-request `trace` of graph steps.
- **Code-enforced loop limit**: the graph cannot spin forever, regardless of
  LLM output.
- **Idempotent ingestion**: deterministic chunk IDs (SHA-256 of
  `source_file::chunk_index`) make re-running the ingest script safe.
- **Free NVIDIA NIM**: chat (`meta/muse-glimmer-30b`) and embeddings
  (`nvidia/llama-nemotron-embed-1b-v2`) share one key, throttled to
  `NIM_RPM_LIMIT` (default 40) by a token-bucket rate limiter.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in Pinecone and NVIDIA NIM keys (one NIM key covers chat + embeddings)
python scripts/ingest_cli.py
./run.sh                    # starts the API server and opens the GUI
```

Or just `./run.sh`: it creates the venv, installs requirements, warns (but
continues) if `.env` is missing, starts the server, and opens the tkinter GUI
(`NO_GUI=1` to skip the GUI, `HOST`/`PORT` to customize).

## Using the API

Three endpoints (full schemas in `API_CONTRACT.md`):

| Endpoint | Request | Response |
|---|---|---|
| `POST /ask` | `{"question": "..."}` | `{answer, citations[], trace[]}` |
| `GET /health` | — | `{"status": "ok"}` |
| `POST /ingest` | — | same pipeline as the CLI (stats) |

```bash
curl -s localhost:8000/health
curl -s localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "What is the notice period in Priya Nambiar's agreement?"}'
```

Interactive docs: `http://localhost:8000/docs`.

Prefer buttons over curl? The tkinter GUI (`scripts/gui_app.py`, opened
automatically by `run.sh`) runs the same curl commands and shows results —
Health / Ingest / Ask buttons, with the exact command printed above each
response.

## Evaluation results (self-test)

`eval/test_cases.json` holds **14 questions** (multi-source, multi-hop, and one
deliberately out-of-corpus) — **all pass**, with a written note per case.
Raw run output: `eval/eval_results.json`. Rerun any time:

```bash
.venv/bin/python eval/run_eval.py          # server must be running
```

Summary of the three refusal cases (all *correct* grounding behavior):

| # | Question | Outcome |
|---|---|---|
| 9 | "Are settlement talks confidential?" | Refused — corpus says "without prejudice", never "confidential" |
| 10 | "Is arbitration required...?" | Refused — statute mandates mediation (Section 14), not arbitration |
| 14 | "Who is the CEO of Acme Corporation?" | Refused — out of corpus, empty citations, trace shows 2 rewrites |

The eval also drove one real fix: section-packing in the chunker (see Design
notes) — it surfaced two answerable questions that were being refused because
headings were detached from their bodies.

## Pinecone checklist

- **Env vars** (in `.env.example`): `PINECONE_API_KEY`, `PINECONE_REGION`,
  `PINECONE_INDEX_NAME` (default `lexcite-index`), `PINECONE_NAMESPACE`
  (default `default`).
- **Index creation**: automatic — the first ingest run creates
  `lexcite-index` (serverless, cosine, dimension = `EMBEDDING_DIMENSION`).
  No manual console step needed. If an index with that name already exists but
  has a different dimension, the client fails loudly with an instruction
  rather than corrupting data.
- **Ingest twice?** Nothing changes: chunk IDs are deterministic, so Pinecone
  `upsert` overwrites by ID. Verified: running the CLI twice back-to-back
  stays at **17 vectors** (no duplicates). Use `--reset` only when the corpus
  itself changed shape — it deletes the namespace first.
- **Verified with real Pinecone**: the ingest CLI reports the vector count
  fetched from Pinecone's own `describe_index_stats`, not a local counter
  (7 files → 17 chunks → 17 vectors).

## Project layout

```
src/
  config.py              # every tunable, env-driven
  ingest/                # loader, chunker, embedder, pinecone client
  graph/                 # state.py, nodes.py, build_graph.py (the graph)
  api/server.py          # FastAPI app (POST /ask, GET /health, POST /ingest)
scripts/
  ingest_cli.py          # one-shot ingestion
  gui_app.py             # tkinter GUI wrapping the same endpoints
eval/
  test_cases.json        # 14 questions + pass/fail notes
  eval_results.json      # raw run output
  run_eval.py            # rerun the self-test
docs/langgraph.md        # node inventory + diagram
PROMPTS.md               # the exact LLM prompts used by each node
API_CONTRACT.md          # request/response schemas
```

## Design notes

- **Chunk size 800 / overlap 120 characters** (env-configurable): the corpus
  is clause-structured legal prose, so the chunker splits on blank lines into
  sections (heading + body), packs paragraphs within a section, and carries
  the document title into every chunk so facts stay attached to their context
  (a deposit figure is only meaningful alongside "Unit 4B, Harbor View
  Tower"). Oversized sections are hard-split at sentence boundaries with
  120 chars of overlap. Character-based rather than token-based sizing
  because the corpus and embeddings cost are small and the boundary logic is
  deterministic and idempotent. Section-packing was added after the eval
  showed whole-paragraph chunks left headings detached from their bodies.
- **Citations are built by code, not by the model**: the model lists which
  chunk numbers it used; code cross-references that list against the actually
  retrieved chunks. A model-fabricated chunk id is dropped and logged, never
  echoed back.
- **Grade parsing fails closed**: unparseable grade JSON is treated as `"bad"`,
  never `"good"`.
- **Rate limiting**: a thread-safe token bucket (burst of `NIM_RPM_LIMIT`,
  continuous refill) sits in front of every NIM chat *and* embedding call —
  chat and embeddings share the same 40 RPM bucket.
- The corpus (`gen_ai_takehome_sample_corpus/`) is the provided fictional
  sample — legal-style documents, all names and facts made up.

## What I skipped

- No auth/rate limiting on the API itself (local demo tool — NIM-side limiting
  is handled).
- No streaming responses.
- `POST /ingest` is optional convenience; the CLI is the primary path.
- Extras from the brief (LangSmith, hybrid search, reranker) not required, not
  built.
- Demo video link: placeholder above — to be filled before submission.
