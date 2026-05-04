#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data
if [[ ! -x .venv/bin/python ]]; then
  if [[ -e .venv ]]; then
    echo "Found .venv, but it does not look like a Linux Python virtual environment."
    echo "Remove .venv or use the Windows scripts, which create .venv-win."
    exit 1
  fi
  uv venv --python 3.12
else
  echo "Reusing existing .venv."
fi
uv sync --extra dev

export WARPARTY_PUBLIC_BASE_URL="${WARPARTY_PUBLIC_BASE_URL:-http://localhost:8080}"
export WARPARTY_PORT="${WARPARTY_PORT:-8080}"

echo "Starting Warparty dev server at http://localhost:${WARPARTY_PORT}"
echo "Press Ctrl+C to stop."
uv run --extra dev uvicorn app.main:app --host 127.0.0.1 --port "$WARPARTY_PORT" --reload
