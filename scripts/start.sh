#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! pgrep -x ollama >/dev/null; then
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 2
fi
source .venv/bin/activate
export PYTHONPATH="$ROOT/backend"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
