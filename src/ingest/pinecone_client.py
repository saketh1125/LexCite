from pinecone import Pinecone, ServerlessSpec

from src.config import (
    EMBEDDING_DIMENSION,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    PINECONE_REGION,
)

BATCH_SIZE = 100


class VectorStore:
    def __init__(self) -> None:
        self.client = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self._ensure_index()

    def _ensure_index(self):
        if PINECONE_INDEX_NAME not in self.client.list_indexes().names():
            self.client.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=PINECONE_REGION),
            )
        return self.client.Index(PINECONE_INDEX_NAME)

    def upsert_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> int:
        vectors = [
            {
                "id": c["chunk_id"],
                "values": emb,
                "metadata": {
                    "source_file": c["source_file"],
                    "chunk_index": c["chunk_index"],
                    "text": c["text"],
                },
            }
            for c, emb in zip(chunks, embeddings)
        ]
        for i in range(0, len(vectors), BATCH_SIZE):
            self.index.upsert(vectors=vectors[i : i + BATCH_SIZE], namespace=PINECONE_NAMESPACE)
        return len(vectors)

    def query(self, embedding: list[float], top_k: int) -> list[dict]:
        resp = self.index.query(
            vector=embedding,
            top_k=top_k,
            namespace=PINECONE_NAMESPACE,
            include_metadata=True,
        )
        return [
            {
                "chunk_id": m.id,
                "source_file": m.metadata.get("source_file", ""),
                "text": m.metadata.get("text", ""),
                "score": m.score,
            }
            for m in resp.matches
        ]

    def reset_namespace(self) -> None:
        self.index.delete(delete_all=True, namespace=PINECONE_NAMESPACE)

    def vector_count(self) -> int:
        stats = self.index.describe_index_stats()
        return stats.namespaces.get(PINECONE_NAMESPACE, {}).get("vector_count", 0)


def run_ingestion(corpus_dir: str | None = None, reset: bool = False) -> dict:
    from src.ingest.chunker import chunk_text
    from src.ingest.embedder import Embedder
    from src.ingest.loader import load_documents

    docs = load_documents(corpus_dir)
    chunks = []
    for doc in docs:
        chunks.extend(chunk_text(doc["raw_text"], doc["source_file"]))
    if not chunks:
        raise RuntimeError("no documents found in corpus directory")
    if reset:
        VectorStore().reset_namespace()
    store = VectorStore()
    embedder = Embedder()
    embeddings = embedder.embed([c["text"] for c in chunks])
    upserted = store.upsert_chunks(chunks, embeddings)
    return {
        "files_processed": len(docs),
        "chunks_created": len(chunks),
        "vectors_upserted": upserted,
        "index_count": store.vector_count(),
    }