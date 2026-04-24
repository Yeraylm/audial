#!/usr/bin/env bash
# ============================================================
# Instalador TFM - Plataforma IA Conversacional (Linux / macOS)
# ============================================================
set -euo pipefail

echo "==> Instalando plataforma IA local"

# 1. Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Instala python3 (3.10+) antes de continuar"
  exit 1
fi

# 2. ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y ffmpeg build-essential
  elif command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "Instala ffmpeg manualmente"; exit 1
  fi
fi

# 3. Ollama
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

# 4. Arrancar Ollama y descargar modelos
if ! pgrep -x ollama >/dev/null; then
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 3
fi
ollama pull llama3:8b
# ollama pull mistral:7b
# ollama pull qwen2.5:7b-instruct

# 5. venv + deps
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# 6. DB
python -c "from backend.app.models import init_db; init_db(); print('DB inicializada')"

echo ""
echo "==> Instalacion completada"
echo "Para arrancar el sistema:"
echo "   source .venv/bin/activate"
echo "   ollama serve &"
echo "   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
echo "Abre http://localhost:8000 en el navegador"
