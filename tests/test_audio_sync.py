"""Sincronización app móvil <-> web: guardar sin analizar, analizar después y metadatos de llamada."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="audial_sync_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(_TMP, 'test.db').as_posix()}")
os.environ.setdefault("PASSWORD_VAULT_KEY", "clave-de-test")
sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.database import SessionLocal, User, init_db  # noqa: E402
from app.routes import audio as audio_routes  # noqa: E402
from app.routes import auth as auth_routes  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402

app = FastAPI()
app.include_router(auth_routes.router)
app.include_router(audio_routes.router)
client = TestClient(app)

analyzed: list[str] = []


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    init_db()
    monkeypatch.setattr(settings, "audio_dir", tmp_path)
    # El pipeline real carga Whisper: aquí solo interesa que se lance (o no)
    monkeypatch.setattr(audio_routes, "process_single_audio",
                        lambda audio_id, *a, **k: analyzed.append(audio_id))
    analyzed.clear()


def _login(email: str, password: str = "clave-123") -> dict:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == email).first():
            db.add(User(email=email, display_name=email.split("@")[0], is_verified=1,
                        hashed_password=hash_password(password)))
            db.commit()
    finally:
        db.close()
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _upload(headers: dict, **form):
    return client.post(
        "/api/audio/upload", headers=headers,
        files={"file": ("call_IN_20261018_143200.m4a", b"fake-m4a-bytes", "audio/m4a")},
        data=form,
    )


def test_store_without_analysis_then_analyze_later():
    h = _login("sync1@test.com")
    r = _upload(h, analyze="false", call_type="incoming", phone_number="+34600111222",
                contact_name="Ana", started_at_ms="1792330320000")
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["stage"] == "stored" and job["status"] == "pending"
    assert analyzed == []                                   # no se ha gastado IA

    items = client.get("/api/audio/", headers=h).json()
    item = next(i for i in items if i["id"] == job["audio_id"])
    assert item["job_id"] == job["id"] and item["job_stage"] == "stored"
    assert (item["call_type"], item["phone_number"], item["contact_name"]) == ("incoming", "+34600111222", "Ana")
    assert item["call_started_at"].startswith("2026-10-")
    assert item["is_guest"] is False

    # el audio se puede descargar (la app lo usa para reproducir lo que viene de la web)
    f = client.get(f"/api/audio/{job['audio_id']}/file")
    assert f.status_code == 200 and f.content == b"fake-m4a-bytes"

    # analizar después reutiliza el mismo job y lanza el pipeline una vez
    a = client.post(f"/api/audio/{job['audio_id']}/analyze", headers=h)
    assert a.status_code == 200
    assert a.json()["id"] == job["id"] and a.json()["stage"] == "queued"
    assert analyzed == [job["audio_id"]]


def test_default_upload_still_analyzes_immediately():
    h = _login("sync2@test.com")
    r = _upload(h)
    assert r.status_code == 200 and r.json()["stage"] == "queued"
    assert analyzed == [r.json()["audio_id"]]


def test_analyze_requires_the_owner():
    owner = _login("sync3@test.com")
    other = _login("sync4@test.com")
    audio_id = _upload(owner, analyze="false").json()["audio_id"]
    assert client.post(f"/api/audio/{audio_id}/analyze", headers=other).status_code == 403
    assert client.post(f"/api/audio/{audio_id}/analyze").status_code == 403       # invitado
    assert client.post("/api/audio/no-existe/analyze", headers=owner).status_code == 404


def test_rename_syncs_contact_name():
    h = _login("sync5@test.com")
    audio_id = _upload(h, analyze="false", contact_name="Antiguo").json()["audio_id"]
    r = client.patch(f"/api/audio/{audio_id}/rename", json={"filename": "Pedro", "contact_name": "Pedro"})
    assert r.status_code == 200 and r.json()["contact_name"] == "Pedro"
    item = next(i for i in client.get("/api/audio/", headers=h).json() if i["id"] == audio_id)
    assert item["contact_name"] == "Pedro" and item["filename"] == "Pedro"


def test_each_account_only_sees_its_own_audios():
    a = _login("sync6@test.com")
    b = _login("sync7@test.com")
    mine = _upload(a, analyze="false").json()["audio_id"]
    ids_b = {i["id"] for i in client.get("/api/audio/", headers=b).json()}
    ids_a = {i["id"] for i in client.get("/api/audio/", headers=a).json()}
    assert mine in ids_a and mine not in ids_b
