import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import src.ingest.embedder as embedder_mod
from src.ingest.embedder import Embedder


class StubClient:
    def __init__(self):
        self.calls = []
        self.embeddings = self

    def create(self, model, input, **kwargs):
        self.calls.append((model, input, kwargs))
        return type("R", (), {"data": [type("D", (), {"embedding": [0.0] * kwargs.get("dimensions", 2048)})() for _ in input]})()


def test_dimensions_param_sent_when_reduced():
    old = embedder_mod.EMBEDDING_DIMENSION
    embedder_mod.EMBEDDING_DIMENSION = 1024
    try:
        stub = StubClient()
        e = Embedder(rate_limiter=embedder_mod.RateLimiter(0))
        e.client = stub
        vectors = e.embed(["a", "b"])
        assert stub.calls[0][2]["dimensions"] == 1024
        assert stub.calls[0][2]["extra_body"]["input_type"] == "passage"
        assert all(len(v) == 1024 for v in vectors)
    finally:
        embedder_mod.EMBEDDING_DIMENSION = old


def test_no_dimensions_param_at_native_size():
    old = embedder_mod.EMBEDDING_DIMENSION
    embedder_mod.EMBEDDING_DIMENSION = 2048
    try:
        stub = StubClient()
        e = Embedder(rate_limiter=embedder_mod.RateLimiter(0))
        e.client = stub
        e.embed(["a"])
        assert "dimensions" not in stub.calls[0][2]
        assert "input_type" not in stub.calls[0][2] or stub.calls[0][2]["extra_body"]["input_type"] == "passage"
    finally:
        embedder_mod.EMBEDDING_DIMENSION = old


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all embedder tests passed")