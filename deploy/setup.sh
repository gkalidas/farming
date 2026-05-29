#!/usr/bin/env bash
# Farming — one-time setup for Ubuntu 22.04 / 24.04
# Run as a regular user (not root). Uses sudo where needed.
# Safe to run multiple times.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/venv"
MODELS_DIR="$REPO_DIR/models"
ENV_FILE="$REPO_DIR/.env"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }

# ── 1. System dependencies ────────────────────────────────────────────────────
info "Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y -q \
    python3.12 python3.12-venv python3.12-dev \
    git curl wget build-essential libgomp1

# ── 2. Python venv + app dependencies ────────────────────────────────────────
info "Setting up Python virtual environment..."
python3.12 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt" -q
info "Python dependencies installed."

# ── 3. Ollama ─────────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    info "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    info "Ollama already installed: $(ollama --version)"
fi

# Start Ollama in background if not running
if ! pgrep -x ollama &>/dev/null; then
    info "Starting Ollama service..."
    nohup ollama serve &>/tmp/ollama.log &
    sleep 3
fi

# ── 4. Ollama models ──────────────────────────────────────────────────────────
# llama3.2:3b  — 2.2GB RAM, fast, good for structured JSON advisory output
# llava:7b     — 4.7GB RAM, vision fallback (only needed if no ONNX model)
# Total with llama3.2:3b only: ~2.2GB — fits well in 12GB
info "Pulling text model (llama3.2:3b — ~2.2GB)..."
ollama pull llama3.2:3b

warn "Vision model (llava:7b) NOT pulled by default."
warn "It is only needed if models/pomegranate.onnx is missing."
warn "To enable: run  ollama pull llava:7b"

# ── 5. App directories ────────────────────────────────────────────────────────
info "Creating app directories..."
mkdir -p "$MODELS_DIR" "$REPO_DIR/uploads" "$REPO_DIR/logs"

# ── 6. Environment file ───────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    info "Creating .env from template..."
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    # Override text model for 12GB RAM machine
    sed -i 's/TEXT_MODEL=.*/TEXT_MODEL=llama3.2:3b/' "$ENV_FILE"
    info ".env created. Edit $ENV_FILE to customise."
else
    warn ".env already exists — skipping. Ensure TEXT_MODEL=llama3.2:3b for 12GB RAM."
fi

# ── 7. Initialise database ────────────────────────────────────────────────────
info "Initialising database..."
cd "$REPO_DIR"
"$VENV_DIR/bin/python" -c "from db.setup import init; init()"
info "Database ready."

# ── 8. ONNX model ─────────────────────────────────────────────────────────────
echo ""
warn "═══════════════════════════════════════════════════════"
warn " MANUAL STEP: copy ONNX model from your Mac"
warn "═══════════════════════════════════════════════════════"
warn " Run this on your MAC:"
warn ""
warn "   scp /path/to/farming/models/pomegranate.onnx      user@<linux-ip>:$MODELS_DIR/"
warn "   scp /path/to/farming/models/pomegranate.onnx.data user@<linux-ip>:$MODELS_DIR/"
warn ""
warn " Both files are required. Without them the app falls"
warn " back to llava:7b (vision LLM — slower, needs 4.7GB)."
warn "═══════════════════════════════════════════════════════"
echo ""

info "Setup complete. Start the server with:"
echo "    ./deploy/start.sh"
echo ""
info "Or install as a systemd service (auto-start on boot):"
echo "    sudo cp $REPO_DIR/deploy/farming.service /etc/systemd/system/"
echo "    sudo sed -i 's|REPO_DIR|$REPO_DIR|g' /etc/systemd/system/farming.service"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl enable --now farming"
