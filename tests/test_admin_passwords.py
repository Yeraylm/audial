"""Contraseñas visibles solo para el owner en el panel de administración BD.

Monta una app mínima (routers auth + admin) sobre una SQLite temporal, así que
no necesita Whisper, Ollama ni el resto de dependencias de IA.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="audial_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["PASSWORD_VAULT_KEY"] = "clave-de-test"
sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.models.database import (  # noqa: E402
    ROLE_ADMIN, ROLE_OWNER, SessionLocal, User, init_db,
)
from app.routes import admin as admin_routes  # noqa: E402
from app.routes import auth as auth_routes  # noqa: E402
from app.services.auth_service import (  # noqa: E402
    decrypt_password, encrypt_password, hash_password,
)

app = FastAPI()
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
client = TestClient(app)


def _make_user(email: str, password: str, role_id: int, with_copy: bool = True) -> str:
    db = SessionLocal()
    try:
        u = User(
            email=email, display_name=email.split("@")[0], role_id=role_id, is_verified=1,
            hashed_password=hash_password(password),
            password_enc=encrypt_password(password) if with_copy else None,
        )
        db.add(u)
        db.commit()
        return u.id
    finally:
        db.close()


def _login(email: str, password: str) -> dict:
    r = client.post("/api/admin/auth", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"X-Admin-Token": r.json()["token"]}


@pytest.fixture(scope="module", autouse=True)
def _seed():
    init_db()
    _make_user("owner@test.com", "owner-pass-1", ROLE_OWNER)
    _make_user("admin@test.com", "admin-pass-1", ROLE_ADMIN)
    _make_user("legacy@test.com", "legacy-pass-1", 3, with_copy=False)


def test_vault_roundtrip():
    enc = encrypt_password("s3creta!")
    assert enc and "s3creta" not in enc
    assert decrypt_password(enc) == "s3creta!"
    assert decrypt_password(None) is None
    assert decrypt_password("basura") is None


def test_owner_sees_plaintext_passwords():
    h = _login("owner@test.com", "owner-pass-1")
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=h).json()}
    assert users["owner@test.com"]["password"] == "owner-pass-1"
    assert users["admin@test.com"]["password"] == "admin-pass-1"
    assert users["legacy@test.com"]["password"] is None   # sin copia todavía


def test_admin_never_sees_passwords():
    h = _login("admin@test.com", "admin-pass-1")
    for u in client.get("/api/admin/users", headers=h).json():
        assert "password" not in u
    t = client.get("/api/admin/tables/users", headers=h).json()
    assert "password" not in t["columns"] and "password_enc" not in t["columns"]
    assert all("password" not in r and "password_enc" not in r for r in t["rows"])
    sql = client.post("/api/admin/sql", headers=h, json={"sql": "SELECT * FROM users"}).json()
    assert "password_enc" not in sql["columns"]


def test_owner_table_view_has_virtual_password_column():
    h = _login("owner@test.com", "owner-pass-1")
    t = client.get("/api/admin/tables/users", headers=h).json()
    assert "password" in t["columns"] and "password_enc" not in t["columns"]
    assert t["columns"].index("password") == t["columns"].index("hashed_password") + 1
    by_email = {r["email"]: r for r in t["rows"]}
    assert by_email["admin@test.com"]["password"] == "admin-pass-1"
    assert all("password_enc" not in r for r in t["rows"])


def test_login_backfills_copy_for_existing_users():
    r = client.post("/api/auth/login", json={"email": "legacy@test.com", "password": "legacy-pass-1"})
    assert r.status_code == 200
    h = _login("owner@test.com", "owner-pass-1")
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=h).json()}
    assert users["legacy@test.com"]["password"] == "legacy-pass-1"


def test_owner_sets_password_from_editor():
    h = _login("owner@test.com", "owner-pass-1")
    uid = next(u["id"] for u in client.get("/api/admin/users", headers=h).json()
               if u["email"] == "admin@test.com")
    r = client.put(f"/api/admin/tables/users/{uid}", headers=h, json={"data": {"password": "nueva-clave-9"}})
    assert r.status_code == 200 and r.json()["changed"] >= 1
    # el login funciona con la nueva y ya no con la vieja; el owner la ve en claro
    assert client.post("/api/auth/login", json={"email": "admin@test.com", "password": "nueva-clave-9"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin-pass-1"}).status_code == 401
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=h).json()}
    assert users["admin@test.com"]["password"] == "nueva-clave-9"


def test_short_password_rejected_and_admin_cannot_set():
    owner = _login("owner@test.com", "owner-pass-1")
    uid = next(u["id"] for u in client.get("/api/admin/users", headers=owner).json()
               if u["email"] == "legacy@test.com")
    assert client.put(f"/api/admin/tables/users/{uid}", headers=owner,
                      json={"data": {"password": "123"}}).status_code == 400
    admin = _login("admin@test.com", "nueva-clave-9")
    assert client.put(f"/api/admin/tables/users/{uid}", headers=admin,
                      json={"data": {"password": "otra-clave-1"}}).status_code == 403


def test_editor_cannot_write_hash_or_copy_directly():
    h = _login("owner@test.com", "owner-pass-1")
    uid = next(u["id"] for u in client.get("/api/admin/users", headers=h).json()
               if u["email"] == "legacy@test.com")
    r = client.put(f"/api/admin/tables/users/{uid}", headers=h,
                   json={"data": {"hashed_password": "x$y", "password_enc": "zzz", "display_name": "Legacy"}})
    assert r.status_code == 200 and r.json()["changed"] == 1   # solo display_name
    assert client.post("/api/auth/login", json={"email": "legacy@test.com", "password": "legacy-pass-1"}).status_code == 200


def test_unknown_columns_are_ignored_and_roles_are_protected():
    owner = _login("owner@test.com", "owner-pass-1")
    admin = _login("admin@test.com", "nueva-clave-9")
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=owner).json()}
    # columna inexistente → ignorada (nada de SQL con nombres arbitrarios)
    r = client.put(f"/api/admin/tables/users/{users['legacy@test.com']['id']}", headers=owner,
                   json={"data": {'x" = 1; --': "boom"}})
    assert r.status_code == 200 and r.json()["changed"] == 0
    # un admin no puede ascenderse a owner ni tocar al owner desde el editor
    assert client.put(f"/api/admin/tables/users/{users['admin@test.com']['id']}", headers=admin,
                      json={"data": {"role_id": 1}}).status_code == 403
    assert client.put(f"/api/admin/tables/users/{users['owner@test.com']['id']}", headers=admin,
                      json={"data": {"display_name": "hack"}}).status_code == 403
    # y el owner no se puede borrar por la vía genérica
    assert client.delete(f"/api/admin/tables/users/{users['owner@test.com']['id']}",
                         headers=owner).status_code == 400


def _user_token(email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_profile_update_name_and_password():
    _make_user("perfil@test.com", "perfil-clave-1", 3)
    h = _user_token("perfil@test.com", "perfil-clave-1")

    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "perfil@test.com" and me["created_at"] and me["is_google"] is False

    r = client.put("/api/auth/me", headers=h, json={"display_name": "  Nuevo Nombre "})
    assert r.status_code == 200 and r.json()["display_name"] == "Nuevo Nombre"
    assert client.put("/api/auth/me", headers=h, json={"display_name": "  "}).status_code == 400

    # cambiar contraseña exige la actual
    assert client.put("/api/auth/me", headers=h, json={"new_password": "otra-clave-2"}).status_code == 403
    assert client.put("/api/auth/me", headers=h, json={
        "current_password": "mala", "new_password": "otra-clave-2"}).status_code == 403
    assert client.put("/api/auth/me", headers=h, json={
        "current_password": "perfil-clave-1", "new_password": "123"}).status_code == 400
    ok = client.put("/api/auth/me", headers=h, json={
        "current_password": "perfil-clave-1", "new_password": "otra-clave-2"})
    assert ok.status_code == 200
    assert client.post("/api/auth/login", json={"email": "perfil@test.com", "password": "otra-clave-2"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "perfil@test.com", "password": "perfil-clave-1"}).status_code == 401


def test_profile_requires_login():
    assert client.put("/api/auth/me", json={"display_name": "x"}).status_code == 401


def test_register_flow_stores_recoverable_copy():
    r = client.post("/api/auth/register", json={
        "email": "nuevo@test.com", "password": "registro-123", "display_name": "Nuevo"})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    v = client.post("/api/auth/verify-code", json={"email": "nuevo@test.com", "code": code})
    assert v.status_code == 200, v.text
    owner = _login("owner@test.com", "owner-pass-1")
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=owner).json()}
    assert users["nuevo@test.com"]["password"] == "registro-123"
