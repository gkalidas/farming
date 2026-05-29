#!/usr/bin/env bash
# Start the Farming server.
# Run from any directory — resolves paths automatically.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/venv"
PORT="${PORT:-5002}"

# Load .env if present
if [ -f "$REPO_DIR/.env" ]; then
    set -a; source "$REPO_DIR/.env"; set +a
fi

# Ensure Ollama is running
if ! pgrep -x ollama &>/dev/null; then
    echo "[start] Starting Ollama..."
    nohup ollama serve &>/tmp/ollama.log &
    sleep 3
fi

echo "[start] Farming server → http://0.0.0.0:$PORT"
cd "$REPO_DIR"
exec "$VENV_DIR/bin/uvicorn" main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1
