from typing import Literal, Optional, TypedDict


class Chunk(TypedDict):
    chunk_id: str
    source_file: str
    text: str
    score: float


class Citation(TypedDict):
    chunk_id: str
    source_file: str
    text_snippet: str


class AgentState(TypedDict, total=False):
    question: str
    search_query: str
    retrieved_chunks: list[Chunk]
    grade: Optional[Literal["good", "bad"]]
    grade_reason: Optional[str]
    attempt: int
    max_attempts: int
    answer: Optional[str]
    citations: list[Citation]
    trace: list[str]