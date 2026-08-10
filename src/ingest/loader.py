from pathlib import Path

from src.config import CORPUS_DIR

EXTENSIONS = {".txt", ".md"}


def load_documents(corpus_dir: Path | None = None) -> list[dict]:
    corpus_dir = Path(corpus_dir or CORPUS_DIR)
    docs = []
    for path in sorted(corpus_dir.rglob("*")):
        if path.suffix.lower() in EXTENSIONS:
            docs.append({"source_file": path.name, "raw_text": path.read_text(encoding="utf-8")})
    return docs