"""Punto de entrada FastAPI.

Levanta la aplicacion, monta las rutas, sirve el frontend estatico y
crea las tablas de la base de datos en el primer arranque.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.models import init_db
from app.routes import analysis, audio, dashboard, search

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Plataforma inteligente de analisis de conversaciones de audio: "
        "transcripcion (Whisper local), analisis semantico con LLM local "
        "(Ollama), diarizacion, busqueda vectorial y arquitectura Big Data."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# --- API routes ---
app.include_router(audio.router)
app.include_router(analysis.router)
app.include_router(search.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}


# --- Static frontend ---
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

if FRONTEND_DIR.exists():
    # Montar subdirectorios para evitar conflictos con rutas /api
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        # favicon inline para evitar 404 (el real viene como SVG dentro del HTML)
        return Response(status_code=204)
else:
    @app.get("/", include_in_schema=False)
    def _missing() -> dict[str, str]:
        return {
            "error": f"Frontend no encontrado en {FRONTEND_DIR}",
            "hint": "Ejecuta desde la raiz del proyecto o verifica PYTHONPATH",
        }
