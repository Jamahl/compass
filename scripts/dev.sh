#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/apps/api"

# Install npm deps if needed
if [ ! -d "$ROOT/node_modules" ]; then
  echo ">>> Installing npm dependencies..."
  npm install --prefix "$ROOT"
fi

# Set up Python venv if needed
if [ ! -f "$API_DIR/.venv/bin/uvicorn" ]; then
  echo ">>> Setting up Python virtual environment..."
  python3 -m venv "$API_DIR/.venv"
  "$API_DIR/.venv/bin/pip" install -e "$API_DIR" --quiet
fi

exec npx concurrently \
  "npm --workspace web run dev" \
  "cd \"$API_DIR\" && .venv/bin/uvicorn main:app --reload --port 8000"
