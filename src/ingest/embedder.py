from openai import OpenAI

from src.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    NIM_RPM_LIMIT,
)
from src.rate_limit import RateLimiter

BATCH_SIZE = 64
NATIVE_DIMENSION = 2048  # llama-nemotron-embed-1b-v2 native output; omit the param at this size

_default_limiter = RateLimiter(NIM_RPM_LIMIT)


class Embedder:
    def __init__(self, rate_limiter: RateLimiter | None = None) -> None:
        self.client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)
        self.rate_limiter = rate_limiter or _default_limiter

    def embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            self.rate_limiter.acquire()
            kwargs = {"extra_body": {"input_type": input_type}}
            if EMBEDDING_DIMENSION != NATIVE_DIMENSION:
                kwargs["dimensions"] = EMBEDDING_DIMENSION
            resp = self.client.embeddings.create(model=EMBEDDING_MODEL, input=batch, **kwargs)
            vectors.extend([item.embedding for item in resp.data])
        return vectors