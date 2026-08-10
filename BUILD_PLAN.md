# BUILD_PLAN.md — Execution Phases

Each phase ends with code that runs, a commit, and a push. Phase guide:
`Phase 1` and `Phase 2` and `Phase 3` can be built and committed independently;
the API only works end-to-end once phases 1–3 exist, but each phase is
runnable on its own (CLI traces, graph unit tests, server boots).

## Phase 0 — Specs & scaffold (this repo state)

- Author the missing spec docs: `API_CONTRACT.md`, `PROMPTS.md`, `BUILD_PLAN.md`.
- `.gitignore` (`.env`, `.venv/`, `__pycache__/`), `requirements.txt`,
  `.env.example` with dummy placeholders.
- Copy `gen_ai_takehome_sample_corpus/` into the repo root.
- Outcome: `git log` shows one commit per deliverable above.

## Phase 1 — Ingestion pipeline

- `src/config.py` — centralized tunables (chunk size/overlap, top_k, max
  attempts, model names, dims) from env with defaults.
- `src/ingest/loader.py` — read corpus dir, `.txt` + `.md`, strip CRLF.
- `src/ingest/chunker.py` — paragraph/boundary-aware split, deterministic
  `sha256(f"{source_file}::{chunk_index}")[:16]` chunk ids.
- `src/ingest/embedder.py` — OpenAI-compatible embeddings wrapper, batched.
- `src/ingest/pinecone_client.py` — index create-if-missing, upsert (≤100/
  batch), query, reset_namespace.
- `scripts/ingest_cli.py` — `--corpus-dir [--reset]`, prints stats from
  Pinecone, not local counters.
- Tests: `test_chunker.py` (determinism, boundary splitting, idempotency
  mechanism), `test_pinecone_client.py` (mock).
- Commit sequence mirrors the phase-1 example in AGENT.md.

## Phase 2 — LangGraph branch

- `src/graph/state.py` — `AgentState` TypedDicts per ARCHITECTURE.md §3.1.
- `src/graph/nodes.py` — `retrieve`, `grade_chunks`, `rewrite_query`,
  `generate_answer`, `cannot_answer`, each appending to `trace`.
- `src/graph/build_graph.py` — StateGraph wiring with
  `route_after_grade` conditional edge; hard `max_attempts` counter in code.
- Tests: `test_graph.py` — route logic (good → answer, bad + attempts left →
  rewrite, exhausted → cannot_answer), no-LLM path shapes.
- Commit as: state, nodes, graph wiring, tests — separate commits.

## Phase 3 — API layer

- `src/api/server.py` — `POST /ask`, `GET /health`, `POST /ingest`.
- Dependency-inject embedder/vectorstore/llm so tests can bypass network.
- 502/503 mapping for upstream failures; 400 for bad question.
- Commit as: server + error handling.

## Phase 4 — Evaluation, docs, cleanup

- `eval/test_cases.json` — 10–15 questions: multi-file, multi-hop, one
  deliberately out-of-corpus; pass/fail notes after live run.
- `README.md` — clone → install → env → ingest → run → call `/ask`.
  "Design notes" (chunk size/overlap justification) and "What I skipped".
- `docs/langgraph.md` — node inventory + diagram.
- Definition-of-done self-check from AGENT.md, then final push.