# API_CONTRACT.md — HTTP API Specification

## POST /ask

Request:

```json
{ "question": "What is the notice period in Priya Nambiar's agreement?" }
```

Response 200:

```json
{
  "answer": "The notice period is 60 days...",
  "citations": [
    {
      "chunk_id": "sha256...[:16]",
      "source_file": "02_employment_agreement_excerpt.md",
      "text_snippet": "Either party may end this agreement by giving **60 days** written notice."
    }
  ],
  "trace": ["retrieve: query='notice period', got 6 chunks, top score=0.83", "grade: good — ..."]
}
```

- `question`: non-empty string. Missing/empty → 400 `{"detail": "question must be a non-empty string"}`.
- `citations`: list of `{chunk_id, source_file, text_snippet}`; every `chunk_id` must be a
  real retrieved chunk id. Empty when the corpus cannot answer.
- `trace`: ordered list of one-line node summaries from `AgentState["trace"]`, used both for
  debugging and as the video-demo walkthrough.

Out-of-corpus questions return 200 with:

```json
{ "answer": "I cannot find this in the provided documents.", "citations": [], "trace": [...] }
```

## GET /health

Response 200:

```json
{ "status": "ok" }
```

## POST /ingest (optional convenience)

Runs the same pipeline as the CLI. Response 200:

```json
{ "status": "ok", "files_processed": 6, "chunks_created": 14, "vectors_upserted": 14, "index_count": 14 }
```

## Errors

| Situation | Status | Body |
|---|---|---|
| Pinecone / embedding / LLM failure | 502 | `{"detail": "upstream service unavailable: <short msg>"}` |
| Empty corpus or empty index on /ask | 200 | The standard "cannot find" answer (retrieval routes to cannot_answer) |
| Invalid JSON body | 400 | `{"detail": "invalid request body"}` |