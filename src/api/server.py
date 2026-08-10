import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.graph.build_graph import run_graph
from src.ingest.pinecone_client import run_ingestion

logger = logging.getLogger("lexcite")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="LexCite")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    citations: list[dict]
    trace: list[str]


class IngestResponse(BaseModel):
    status: str
    files_processed: int
    chunks_created: int
    vectors_upserted: int
    index_count: int


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> dict:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must be a non-empty string")
    try:
        result = run_graph(question=question)
    except Exception as exc:
        logger.exception("ask failed")
        raise HTTPException(status_code=502, detail=f"upstream service unavailable: {exc}")
    for line in result["trace"]:
        logger.info("trace | %s", line)
    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "trace": result["trace"],
    }


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> dict:
    try:
        result = run_ingestion()
    except Exception as exc:
        logger.exception("ingest failed")
        raise HTTPException(status_code=502, detail=f"upstream service unavailable: {exc}")
    return {"status": "ok", **result}