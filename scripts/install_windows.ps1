# ============================================================
# Instalador TFM - Plataforma IA Conversacional (Windows)
# ============================================================
# Ejecutar en PowerShell como Administrador si es posible:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\scripts\install_windows.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Write-Host "==> Instalando plataforma IA local" -ForegroundColor Cyan

# ------ 1. Python ------
$pyVersion = (python --version) 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python no encontrado. Instalalo desde https://python.org (3.10+)"
    exit 1
}
Write-Host "Python OK: $pyVersion" -ForegroundColor Green

# ------ 2. ffmpeg (requerido por Whisper/pydub) ------
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Host "ffmpeg no encontrado. Instalando via winget..."
    winget install --id=Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
} else {
    Write-Host "ffmpeg OK" -ForegroundColor Green
}

# ------ 3. Ollama ------
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama no encontrado. Instalando via winget..."
    winget install --id=Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
} else {
    Write-Host "Ollama OK" -ForegroundColor Green
}

# ------ 4. Modelos LLM ------
Write-Host "==> Descargando modelos LLM (puede tardar)" -ForegroundColor Cyan
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 3
ollama pull llama3:8b
# ollama pull mistral:7b
# ollama pull qwen2.5:7b-instruct

# ------ 5. venv + deps ------
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

# ------ 6. Crear BD (SQLite por defecto) ------
python -c "from backend.app.models import init_db; init_db(); print('DB inicializada')"

Write-Host ""
Write-Host "==> Instalacion completada" -ForegroundColor Green
Write-Host "Para arrancar el sistema:"
Write-Host "   .\.venv\Scripts\Activate.ps1"
Write-Host "   ollama serve   # en otra terminal"
Write-Host "   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
Write-Host "Abre http://localhost:8000 en el navegador"
