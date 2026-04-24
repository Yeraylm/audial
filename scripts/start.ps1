# Arranque rapido en Windows con Ollama + FastAPI
# --reload-dir backend: solo recarga cuando cambia codigo del backend (ignora .venv)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
    Write-Host "Arrancando Ollama en segundo plano..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

$env:PYTHONPATH = "$root\backend"
Write-Host "Servidor en http://localhost:8000"
Write-Host "Logs disponibles en consola del navegador (F12 > Console)"
Write-Host ""

.\.venv\Scripts\python.exe -m uvicorn app.main:app `
    --host 0.0.0.0 `
    --port 8000 `
    --reload `
    --reload-dir backend `
    --log-level info
