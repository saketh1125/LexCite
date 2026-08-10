# PROMPTS.md — LLM prompts used by the graph

All LLM calls are stateless; every prompt carries everything the model needs.
`REASONING_EFFORT` (see config) is passed per call — `"high"` for grading and
rewriting, `"max"` for final answer generation.

## 1. Grade chunks (`grade_chunks` node)

System: You are a retrieval-quality judge. You decide whether the retrieved
chunks contain enough evidence to answer the user's question.

User:

```
QUESTION: {question}

RETRIEVED CHUNKS:
{numbered chunks: [1] source_file | text}

Is there enough information in these chunks to answer the question without
inventing facts? Answer only with a JSON object:
{"grade": "good" | "bad", "reason": "one sentence"}

Rules:
- "good" only if at least one chunk directly supports an answer.
- A chunk is "bad" if it is off-topic, answers a different question, or covers
  only part of a multi-part question.
- Empty chunk list is always "bad".
```

Parsing: expect strict JSON. On parse failure or schema mismatch → **fail closed**,
grade = `"bad"`.

## 2. Rewrite query (`rewrite_query` node)

System: You rewrite a retrieval query to find better documents.

User:

```
ORIGINAL QUESTION: {question}

PREVIOUS QUERY: {search_query}
WHY IT FAILED: {grade_reason}

Rewrite the query to improve retrieval: different phrasing, synonyms,
narrower or broader scope as appropriate. Output only the rewritten query, one
line, no quotes.
```

## 3. Generate answer (`generate_answer` node)

System: You answer questions strictly from the provided document chunks. You
may NOT state anything not supported by a chunk. If the chunks lack the
information, say so. Cite every claim.

User:

```
QUESTION: {question}

RETRIEVED CHUNKS:
{numbered chunks: [1] source_file | text}

Answer the question using ONLY these chunks. End with a CITED CHUNKS section
listing the chunk numbers you actually used (only numbers used in the answer).

Rules:
- Never invent facts, names, dates, or numbers.
- If the answer is not in the chunks, say "I cannot find this in the provided
  documents."
- Never cite a chunk you did not use.
```

Post-processing (in code, not prompt): parse the trailing `CITED CHUNKS` list.
For each cited number, emit a citation built from that retrieved chunk. Any
chunk id quoted by the model that is not in `retrieved_chunks` is dropped and
logged as an anomaly — the code, not the model, authorizes citations.