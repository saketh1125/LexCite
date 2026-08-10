# LangGraph internals

## Graph

```
START
  │
  ▼
retrieve ──────────────► grade_chunks
  ▲                            │
  │   (grade == "bad"          │ (grade == "good")
  │    and attempt <           ▼
  │    max_attempts)      generate_answer ──► END
  │                            │
  └──────── rewrite_query      │ (grade == "bad", attempts exhausted)
                              ▼
                         cannot_answer ──► END
```

| Node | What it does | Output fields it sets |
|---|---|---|
| `retrieve` | Embeds `search_query`, queries Pinecone (top_k from config), writes matches into state, appends a trace line with top score. | `retrieved_chunks`, `trace` |
| `grade_chunks` | Separate LLM call (PROMPTS.md §1) judges whether the chunks can answer the question. Strict JSON `{"grade": "good"|"bad", "reason"}`; unparseable output **fails closed to "bad"**. Empty chunk list is graded "bad" without an LLM call. | `grade`, `grade_reason`, `trace` |
| `rewrite_query` | LLM reformulates the query (PROMPTS.md §2), increments `attempt` (the single place the counter changes), routes back to `retrieve`. | `search_query`, `attempt`, `trace` |
| `generate_answer` | LLM answers from chunks only (PROMPTS.md §3) and ends with a `CITED: n, m` line. Code builds citations from the numbers, cross-referencing against `retrieved_chunks`; any nonexistent number is dropped and logged as an anomaly. | `answer`, `citations`, `trace` |
| `cannot_answer` | Deterministic, no LLM: fixed "cannot find" answer, empty citations. | `answer`, `citations`, `trace` |

## Loop safety — by construction, not by prompt

`route_after_grade` (src/graph/build_graph.py) is the only legal way flow
leaves `grade_chunks`: "good" → answer, "bad" with `attempt < max_attempts` →
rewrite, otherwise → cannot_answer. `rewrite_query` always routes back to
`retrieve`, so the maximum number of retrieval passes per request is
`max_attempts + 1`. The graph is additionally invoked with a recursion limit
of `(max_attempts + 1) * 4` as a second, independent safety net.

## State

`AgentState` (src/graph/state.py) carries: `question` (never mutated),
`search_query`, `retrieved_chunks`, `grade`, `grade_reason`, `attempt`,
`max_attempts`, `answer`, `citations`, `trace`. Every node returns only the
fields it owns; LangGraph merges them.