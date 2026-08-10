from openai import OpenAI

from src.config import EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL

BATCH_SIZE = 64


class Embedder:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            resp = self.client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            vectors.extend([item.embedding for item in resp.data])
        return vectors