#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found in PATH" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "==> .venv missing — creating and installing requirements"
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
elif ! .venv/bin/python -c "import fastapi, uvicorn, langgraph, pinecone" 2>/dev/null; then
  echo "==> requirements missing in .venv — installing"
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "WARNING: .env not found — copy .env.example to .env and fill in your keys first" >&2
fi

echo
echo "==> Starting LexCite API server on http://$HOST:$PORT"
echo
echo "    Try these URLs:"
echo "      Interactive docs : http://$HOST:$PORT/docs"
echo "      ReDoc            : http://$HOST:$PORT/redoc"
echo "      OpenAPI JSON     : http://$HOST:$PORT/openapi.json"
echo "      Health check     : curl -s http://$HOST:$PORT/health"
echo "      Ask a question   : curl -s http://$HOST:$PORT/ask -H 'Content-Type: application/json' -d '{\"question\": \"What is the notice period in Priya Nambiar\\'s agreement?\"}'"
echo
echo "    Everything need a key? Run: .venv/bin/python scripts/ingest_cli.py"
echo "    Stop with Ctrl+C."
echo

if [ -z "${NO_GUI:-}" ] && [ -n "${DISPLAY:-}" ]; then
  echo "==> Opening the tkinter GUI (disable with NO_GUI=1 ./run.sh)"
  nohup .venv/bin/python scripts/gui_app.py "http://$HOST:$PORT" >/dev/null 2>&1 &
elif [ -n "${NO_GUI:-}" ]; then
  echo "(GUI skipped: NO_GUI=1)"
fi

exec .venv/bin/uvicorn src.api.server:app --host "$HOST" --port "$PORT"