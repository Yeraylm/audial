"""Punto de entrada FastAPI."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.models import init_db
from app.routes import analysis, audio, dashboard, search
from app.routes import auth as auth_routes
from app.routes import admin as admin_routes
from app.services.guest_cleanup import run_periodic_cleanup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    # Tarea de limpieza: cada hora elimina audios de invitado expirados
    cleanup_task = asyncio.create_task(run_periodic_cleanup(3600))
    yield
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Plataforma IA de análisis de conversaciones de audio.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(audio.router)
app.include_router(analysis.router)
app.include_router(search.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

if FRONTEND_DIR.exists():
    for sub in ("css", "js", "assets"):
        sub_dir = FRONTEND_DIR / sub
        sub_dir.mkdir(exist_ok=True)
        app.mount(f"/{sub}", StaticFiles(directory=sub_dir), name=sub)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    @app.get("/admin", include_in_schema=False)
    def admin_page() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "admin.html",
                            headers={"Cache-Control": "no-store"})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)
else:
    @app.get("/", include_in_schema=False)
    def _missing() -> dict[str, str]:
        return {"error": f"Frontend not found at {FRONTEND_DIR}"}
