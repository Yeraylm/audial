"""Pruebas 'humo' minimas: verifican que el backend arranca y responde.

Estos tests NO requieren Ollama ni Whisper cargados; solo comprueban
que la aplicacion FastAPI levanta, la base de datos se inicializa y los
endpoints devuelven la estructura esperada.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_audios_empty_or_not():
    r = client.get("/api/audio/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_dashboard_overview():
    r = client.get("/api/dashboard/overview")
    assert r.status_code == 200
    data = r.json()
    assert "total_audios" in data
    assert "sentiment_distribution" in data
