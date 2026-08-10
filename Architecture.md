# ARCHITECTURE.md — Technical Design

## 1. System overview

```
 corpus/*.txt/.md
        │
        ▼
   [ INGEST PIPELINE ]  (CLI, run once or on demand)
   load → chunk → embed → upsert to Pinecone
        │
        ▼
   [ PINECONE INDEX ]  (persistent vector store, metadata attached)
        ▲
        │  query
   [ LANGGRAPH ]  (invoked per request)
   retrieve → grade_chunks → (branch) → generate_answer | rewrite_query → cannot_answer
        ▲
        │
   [ FASTAPI ]  POST /ask, GET /health, (optional) POST /ingest
        ▲
        │
      client (curl / Postman)
```

## 2. Ingestion pipeline

### 2.1 Loader (`src/ingest/loader.py`)
- Reads every file in the corpus directory (configurable path, default
  `./gen_ai_takehome_sample_corpus/`).
- Supports `.txt` and `.md` at minimum (check the sample zip's actual extensions and
  support what's there).
- Returns a list of `{source_file: str, raw_text: str}`.

### 2.2 Chunker (`src/ingest/chunker.py`)
- Split by paragraph/section boundaries first, then enforce a max token/character size
  with overlap, rather than a naive fixed-width split — legal-style notes have clause
  structure worth preserving.
- Defaults: `chunk_size = 800` characters, `chunk_overlap = 120` characters. Expose both
  as env-configurable constants in `config.py`. Document the choice in the README
  ("Design notes") — this is a place reviewers expect a justified, not arbitrary, choice.
- **Deterministic chunk ID**: `chunk_id = sha256(f"{source_file}::{chunk_index}").hexdigest()[:16]`.
  This is the mechanism that makes re-ingestion idempotent — Pinecone `upsert` with an
  existing ID overwrites rather than duplicates.
- Output per chunk: `{chunk_id, source_file, chunk_index, text, char_start, char_end}`.

### 2.3 Embedder (`src/ingest/embedder.py`)
- Thin wrapper around whatever embedding provider you use (this can be a separate key
  from the DeepSeek chat key — e.g. an OpenAI-compatible embeddings endpoint, or
  whatever your Pinecone/embedding setup supports). Expose `embed(texts: list[str]) ->
  list[list[float]]`, batch where possible.
- Record the embedding dimension in `config.py` — it must match the Pinecone index's
  configured dimension exactly, or index creation/queries will fail.

### 2.4 Pinecone client (`src/ingest/pinecone_client.py`)
- `create_index_if_not_exists(name, dimension, metric="cosine")` — serverless spec,
  region from env.
- `upsert_chunks(chunks, embeddings, namespace)` — batches of ≤100 vectors per call.
  Vector `id = chunk_id`. Metadata = `{source_file, chunk_index, text}` (storing raw
  text in metadata avoids a second lookup when building citations).
- `query(embedding, top_k, namespace) -> list[match]` — each match has `id`, `score`,
  `metadata`.
- `reset_namespace(namespace)` — deletes all vectors in the namespace; used by
  `--reset` flag on the ingest CLI.
- **Idempotency contract** (must be stated in README): running ingest twice with the
  same corpus and no `--reset` flag results in the same vector count, because upsert
  overwrites by deterministic ID. Running with `--reset` clears the namespace first,
  useful when the corpus itself has changed shape (renamed/removed files).

### 2.5 Ingest CLI (`scripts/ingest_cli.py`)
- `python scripts/ingest_cli.py --corpus-dir ./gen_ai_takehome_sample_corpus [--reset]`
- Prints a summary: files processed, chunks created, vectors upserted, final index
  vector count (fetched from Pinecone stats, not just a local counter — this proves the
  write actually landed).

## 3. LangGraph — state, nodes, edges

### 3.1 State (`src/graph/state.py`)

```python
from typing import TypedDict, Literal, Optional

class Chunk(TypedDict):
    chunk_id: str
    source_file: str
    text: str
    score: float

class Citation(TypedDict):
    chunk_id: str
    source_file: str
    text_snippet: str

class AgentState(TypedDict):
    question: str                  # original user question, never mutated
    search_query: str              # current query used for retrieval, may be rewritten
    retrieved_chunks: list[Chunk]
    grade: Optional[Literal["good", "bad"]]
    grade_reason: Optional[str]
    attempt: int                   # starts at 0, incremented on each rewrite
    max_attempts: int              # hard cap, default 2 (i.e. up to 3 retrieval passes total)
    answer: Optional[str]
    citations: list[Citation]
    trace: list[str]               # human-readable log, one entry appended per node
```

### 3.2 Nodes (`src/graph/nodes.py`)

**`retrieve(state) -> state`**
- Embed `state["search_query"]`.
- Query Pinecone, `top_k` from config (default 6).
- Write results into `retrieved_chunks` (id, source_file, text, score).
- Append to trace: `f"retrieve: query={search_query!r}, got {n} chunks, top score={score}"`.

**`grade_chunks(state) -> state`**
- Separate LLM call (see `PROMPTS.md` for exact prompt). Input: question + retrieved
  chunks. Output: strict JSON `{"grade": "good"|"bad", "reason": "..."}`, parsed and
  validated — do not free-text parse with regex if avoidable; ask the model for JSON
  and validate with a schema, falling back to "bad" if parsing fails (fail closed, not
  open — an unparseable grade should never be treated as "good").
- Append to trace: `f"grade: {grade} — {reason}"`.

**Conditional edge (in `build_graph.py`, not a separate node — this is graph wiring)**

```python
def route_after_grade(state: AgentState) -> str:
    if state["grade"] == "good":
        return "generate_answer"
    if state["attempt"] < state["max_attempts"]:
        return "rewrite_query"
    return "cannot_answer"
```

This function is the "branch" the assignment scoring rubric refers to. Wire it with
`graph.add_conditional_edges("grade_chunks", route_after_grade, {...})`.

**`rewrite_query(state) -> state`**
- Increment `attempt` here (this is the single place the counter changes — makes the
  loop guard easy to audit).
- LLM call: given the original question and why the last attempt was graded "bad",
  produce a reformulated search query (different phrasing, synonyms, or narrower/
  broader scope as appropriate). See `PROMPTS.md`.
- Set `search_query` to the new value; loop back to `retrieve`.
- Append to trace: `f"rewrite_query (attempt {attempt}): {old!r} -> {new!r}"`.

**`generate_answer(state) -> state`**
- LLM call with strict grounding instructions (see `PROMPTS.md`). Must produce prose
  answer plus a structured citation list built from the actual `retrieved_chunks` used
  — do not let the model invent chunk_ids; the citation list should be constructed by
  the code cross-referencing which chunks the model's answer actually drew on (or, at
  minimum, validated post-hoc: any `chunk_id` in the model's output that isn't in
  `retrieved_chunks` is dropped and logged as an anomaly).
- Append to trace: `"generate_answer: produced answer with N citations"`.

**`cannot_answer(state) -> state`**
- Deterministic, no LLM call needed (or a trivial templated one): sets
  `answer = "I cannot find this in the provided documents."`, `citations = []`.
- Append to trace: `f"cannot_answer: exhausted {max_attempts} attempts, last grade=bad"`.

### 3.3 Graph wiring (`src/graph/build_graph.py`)

```
START -> retrieve -> grade_chunks -> [conditional] -> generate_answer -> END
                                    -> rewrite_query -> retrieve (loop)
                                    -> cannot_answer -> END
```

- Use `langgraph.graph.StateGraph(AgentState)`.
- The loop guard is structural: `rewrite_query` always routes back to `retrieve`, and
  `route_after_grade` can only send flow to `rewrite_query` while `attempt <
  max_attempts` — so the maximum number of `retrieve` calls per request is
  `max_attempts + 1`, guaranteed by construction, not by prompting.
- Compile with a recursion limit as defense in depth (`graph.compile()` then pass
  `config={"recursion_limit": (max_attempts + 1) * 4}` or similar generous-but-finite
  bound when invoking) — this is a second, independent safety net, not a substitute for
  the state-based guard above.

## 4. API layer (`src/api/`)

See `API_CONTRACT.md` for exact request/response schemas. Summary:
- `POST /ask` — the only required endpoint. Runs the compiled graph, returns answer +
  citations + trace.
- `GET /health` — trivial liveness check, also useful for the video demo.
- `POST /ingest` — optional; if you build it, it should call the same ingestion
  pipeline as the CLI (don't duplicate logic — CLI and route both call the same
  `run_ingestion()` function in `src/ingest/`).

## 5. Error handling

- Pinecone/embedding/LLM call failures should return HTTP 502/503 with a clear JSON
  error body, not a raw stack trace, and should still be visible in server logs.
- Empty corpus / empty index: `retrieve` returning zero chunks should route straight to
  a "bad" grade (or skip grading and go direct to `cannot_answer` after max attempts) —
  don't let an empty-chunks case crash the grading prompt.
- Malformed grade-JSON from the LLM: fail closed to `"bad"` (see 3.2).

## 6. Logging / trace

- `trace` in the response is the ordered list of one-line node summaries described
  above — this doubles as your video-demo talking points ("here you can see the graph
  chose the retry path because...").
- Server-side, log the same trace lines plus latency per node, to stdout at minimum.

## 7. Config (`src/config.py`)

Centralize every tunable: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K`, `MAX_ATTEMPTS`,
`EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE`,
`DEEPSEEK_MODEL` (`deepseek-v4-flash`), `REASONING_EFFORT` (`"high"` for grading/
rewriting, consider `"max"` for final answer generation where grounding precision
matters most — this is a real per-call tunable on this model, use it deliberately
rather than uniformly).