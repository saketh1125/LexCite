import json
import logging
import re
from typing import Optional

from openai import OpenAI

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_ATTEMPTS,
    REASONING_EFFORT,
    TOP_K,
)
from src.graph.state import AgentState
from src.ingest.embedder import Embedder
from src.ingest.pinecone_client import VectorStore

logger = logging.getLogger("lexcite")

GRADE_PROMPT = """You are a retrieval-quality judge. You decide whether the retrieved
chunks contain enough evidence to answer the user's question.

QUESTION: {question}

RETRIEVED CHUNKS:
{chunks}

Is there enough information in these chunks to answer the question without
inventing facts? Answer only with a JSON object:
{{"grade": "good" | "bad", "reason": "one sentence"}}

Rules:
- "good" only if at least one chunk directly supports an answer.
- A chunk is "bad" if it is off-topic, answers a different question, or covers
  only part of a multi-part question.
- Empty chunk list is always "bad".
"""

REWRITE_PROMPT = """You rewrite a retrieval query to find better documents.

ORIGINAL QUESTION: {question}

PREVIOUS QUERY: {search_query}
WHY IT FAILED: {grade_reason}

Rewrite the query to improve retrieval: different phrasing, synonyms,
narrower or broader scope as appropriate. Output only the rewritten query,
one line, no quotes.
"""

ANSWER_PROMPT = """You answer questions strictly from the provided document chunks. You may
NOT state anything not supported by a chunk. If the chunks lack the
information, say so. Cite every claim.

QUESTION: {question}

RETRIEVED CHUNKS:
{chunks}

Answer the question using ONLY these chunks. End with a line:
CITED: <chunk numbers you actually used, comma separated>

Rules:
- Never invent facts, names, dates, or numbers.
- If the answer is not in the chunks, say "I cannot find this in the provided
  documents."
- Never cite a chunk you did not use.
"""


class GraphDeps:
    def __init__(self) -> None:
        self.embedder = Embedder()
        self.vectorstore = VectorStore()
        self.llm = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL

    def chat(self, system: str, user: str) -> str:
        kwargs = {}
        if REASONING_EFFORT:
            kwargs["extra_body"] = {"reasoning_effort": REASONING_EFFORT}
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            **kwargs,
        )
        return resp.choices[0].message.content or ""


def _numbered(chunks: list[dict]) -> str:
    return "\n".join(
        f"[{i}] {c['source_file']} | {c['text']}" for i, c in enumerate(chunks, 1)
    )


def make_nodes(deps: GraphDeps):
    def retrieve(state: AgentState) -> AgentState:
        query = state["search_query"]
        embedding = deps.embedder.embed([query])[0]
        chunks = deps.vectorstore.query(embedding, TOP_K)
        top = chunks[0]["score"] if chunks else 0.0
        return {
            "retrieved_chunks": chunks,
            "trace": [f"retrieve: query={query!r}, got {len(chunks)} chunks, top score={top}"],
        }

    def grade_chunks(state: AgentState) -> AgentState:
        chunks = state["retrieved_chunks"]
        if not chunks:
            return {
                "grade": "bad",
                "grade_reason": "no chunks retrieved",
                "trace": ["grade: bad — no chunks retrieved"],
            }
        try:
            raw = deps.chat("You are a retrieval-quality judge.", GRADE_PROMPT.format(
                question=state["question"], chunks=_numbered(chunks)
            ))
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {}
            grade = parsed.get("grade")
            reason = parsed.get("reason", "malformed grade JSON")
            grade = grade if grade in ("good", "bad") else "bad"
        except Exception:
            logger.warning("unparseable grade JSON, failing closed to bad", exc_info=True)
            grade, reason = "bad", "unparseable grade JSON"
        return {
            "grade": grade,
            "grade_reason": reason,
            "trace": [f"grade: {grade} — {reason}"],
        }

    def rewrite_query(state: AgentState) -> AgentState:
        old = state["search_query"]
        new = deps.chat(
            "You rewrite retrieval queries.",
            REWRITE_PROMPT.format(
                question=state["question"],
                search_query=old,
                grade_reason=state.get("grade_reason", "unspecified"),
            ),
        ).strip()
        attempt = state.get("attempt", 0) + 1
        return {
            "search_query": new,
            "attempt": attempt,
            "trace": [f"rewrite_query (attempt {attempt}): {old!r} -> {new!r}"],
        }

    def generate_answer(state: AgentState) -> AgentState:
        chunks = state["retrieved_chunks"]
        raw = deps.chat("You answer only from provided chunks.", ANSWER_PROMPT.format(
            question=state["question"], chunks=_numbered(chunks)
        ))
        cited = []
        cited_line = re.search(r"CITED:\s*(.+)", raw)
        if cited_line:
            for n in re.findall(r"\d+", cited_line.group(1)):
                idx = int(n) - 1
                if 0 <= idx < len(chunks):
                    c = chunks[idx]
                    cited.append({
                        "chunk_id": c["chunk_id"],
                        "source_file": c["source_file"],
                        "text_snippet": c["text"],
                    })
                else:
                    logger.warning("model cited nonexistent chunk number %s; dropped", n)
        answer = re.sub(r"\s*CITED:.*$", "", raw, flags=re.DOTALL).strip()
        return {
            "answer": answer,
            "citations": cited,
            "trace": [f"generate_answer: produced answer with {len(cited)} citations"],
        }

    def cannot_answer(state: AgentState) -> AgentState:
        return {
            "answer": "I cannot find this in the provided documents.",
            "citations": [],
            "trace": [
                f"cannot_answer: exhausted {state.get('max_attempts', MAX_ATTEMPTS)} attempts, last grade=bad"
            ],
        }

    return {
        "retrieve": retrieve,
        "grade_chunks": grade_chunks,
        "rewrite_query": rewrite_query,
        "generate_answer": generate_answer,
        "cannot_answer": cannot_answer,
    }