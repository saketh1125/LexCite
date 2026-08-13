import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.build_graph import build_graph, route_after_grade


class FakeDeps:
    def __init__(self, grades, answers=None):
        self.grades = grades
        self.answers = answers or {}
        self.calls = []

    def chat(self, system, user):
        self.calls.append(user)
        if len(self.calls) <= len(self.grades):
            return self.grades[len(self.calls) - 1]
        return self.answers.get(len(self.calls), "rewritten query")


class FakeEmbedder:
    def embed(self, texts, input_type="passage"):
        return [[0.0] * 8 for _ in texts]


class FakeVectorStore:
    def __init__(self, chunks=None):
        self.chunks = chunks or []

    def query(self, embedding, top_k):
        return self.chunks[:top_k]


def state(**over):
    s = {
        "question": "q", "search_query": "q", "attempt": 0, "max_attempts": 2,
        "retrieved_chunks": [], "citations": [], "trace": [],
    }
    s.update(over)
    return s


def test_routing():
    good = state(grade="good")
    bad_retry = state(grade="bad", attempt=1, max_attempts=2)
    bad_exhausted = state(grade="bad", attempt=2, max_attempts=2)
    assert route_after_grade(good) == "generate_answer"
    assert route_after_grade(bad_retry) == "rewrite_query"
    assert route_after_grade(bad_exhausted) == "cannot_answer"


def test_good_path_has_answer_and_citations():
    chunk = {"chunk_id": "abc", "source_file": "f.md", "text": "60 days notice.", "score": 0.9}
    deps = FakeDeps(
        grades=['{"grade": "good", "reason": "covers it"}'],
        answers={2: "The notice period is 60 days.\nCITED: 1"},
    )
    deps.embedder, deps.vectorstore = FakeEmbedder(), FakeVectorStore([chunk])
    out = build_graph(deps).invoke(state(retrieved_chunks=[chunk]), config={"recursion_limit": 20})
    assert out["answer"] == "The notice period is 60 days."
    assert out["citations"] == [{"chunk_id": "abc", "source_file": "f.md", "text_snippet": "60 days notice."}]


def test_bad_retry_loop_then_cannot_answer():
    deps = FakeDeps(grades=["bad"] * 3)
    deps.embedder, deps.vectorstore = FakeEmbedder(), FakeVectorStore([])
    out = build_graph(deps).invoke(state(), config={"recursion_limit": 20})
    assert out["answer"] == "I cannot find this in the provided documents."
    assert out["citations"] == []
    assert out["attempt"] == 2


def test_model_cannot_fabricate_citation():
    chunk = {"chunk_id": "abc", "source_file": "f.md", "text": "x", "score": 0.9}
    deps = FakeDeps(
        grades=['{"grade": "good", "reason": "ok"}'],
        answers={2: "Answer.\nCITED: 1, 99"},
    )
    deps.embedder, deps.vectorstore = FakeEmbedder(), FakeVectorStore([chunk])
    out = build_graph(deps).invoke(state(retrieved_chunks=[chunk]), config={"recursion_limit": 20})
    assert [c["chunk_id"] for c in out["citations"]] == ["abc"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all graph tests passed")