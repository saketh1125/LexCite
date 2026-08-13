import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.pinecone_client import run_ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the corpus into Pinecone")
    parser.add_argument("--corpus-dir", default=None, help="corpus directory (default: config)")
    parser.add_argument("--reset", action="store_true", help="clear the namespace first")
    args = parser.parse_args()

    result = run_ingestion(corpus_dir=args.corpus_dir, reset=args.reset)
    print(
        f"files processed: {result['files_processed']}\n"
        f"chunks created: {result['chunks_created']}\n"
        f"vectors upserted: {result['vectors_upserted']}\n"
        f"index count (from Pinecone): {result['index_count']}"
    )


if __name__ == "__main__":
    main()