"""Panel de administración de base de datos.

Acceso exclusivo para usuarios con rol 'owner' o 'admin'.
Fallback de emergencia: ADMIN_SECRET env var (para bootstrap inicial).

Solo el 'owner' ve las contraseñas en claro (copia cifrada `users.password_enc`,
descifrada al vuelo) y puede establecer una nueva desde el editor de filas.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database import (
    ROLE_ADMIN, ROLE_OWNER, ROLE_USER,
    Role, User, get_db, engine, SessionLocal,
)
from app.services.auth_service import (
    create_token, decode_token, decrypt_password, encrypt_password,
    hash_password, sync_password_copy, verify_password,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "audial-admin-2026")


# ── Auth helpers ──────────────────────────────────────────────────────
def _get_admin_from_header(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token")
) -> dict:
    """Valida el token: puede ser ADMIN_SECRET (emergencia) o JWT de admin/owner."""
    if not x_admin_token:
        raise HTTPException(403, "Se requiere token de administrador")
    # Emergencia: ADMIN_SECRET raw
    if x_admin_token == ADMIN_SECRET:
        return {"role": "owner", "email": "system", "user_id": None}
    # JWT de usuario con rol admin/owner
    try:
        payload = decode_token(x_admin_token)
        user_id = payload.get("sub")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_admin:
                raise HTTPException(403, "Tu cuenta no tiene permisos de administrador")
            return {"role": user.role_name, "email": user.email, "user_id": user.id}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(403, "Token inválido o sin permisos de administrador")


AdminDep = Depends(_get_admin_from_header)

# Columna interna con la copia cifrada: nunca se expone tal cual
_SECRET_COL = "password_enc"


def _is_owner(admin_info: dict) -> bool:
    return admin_info.get("role") == "owner"


class AuthIn(BaseModel):
    email:    str | None = None
    password: str | None = None
    secret:   str | None = None   # ADMIN_SECRET de emergencia


@router.post("/auth")
def admin_auth(body: AuthIn, db: Session = Depends(get_db)):
    """Login al panel admin: email+password (si es admin/owner) o ADMIN_SECRET."""
    # Emergencia con ADMIN_SECRET
    if body.secret and body.secret == ADMIN_SECRET:
        return {"token": ADMIN_SECRET, "role": "owner", "email": "system", "ok": True}

    # Login normal: email + password
    if not body.email or not body.password:
        raise HTTPException(400, "Proporciona email y contraseña, o la clave de emergencia")

    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Email o contraseña incorrectos")
    if not user.is_admin:
        raise HTTPException(403, f"Tu cuenta tiene rol '{user.role_name}'. Solo admins y propietarios pueden entrar.")

    if sync_password_copy(user, body.password):
        db.commit()
    return {
        "token": create_token(user.id, user.email),
        "role": user.role_name, "email": user.email,
        "display_name": user.display_name, "ok": True,
    }


# ── Roles ─────────────────────────────────────────────────────────────
@router.get("/roles", dependencies=[AdminDep])
def list_roles(db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name, "description": r.description}
            for r in db.query(Role).order_by(Role.id).all()]


# ── Users ─────────────────────────────────────────────────────────────
@router.get("/users")
def list_users(admin_info: dict = AdminDep, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    roles = {r.id: r.name for r in db.query(Role).all()}
    owner = _is_owner(admin_info)
    out = []
    for u in users:
        row = {
            "id": u.id, "email": u.email, "display_name": u.display_name,
            "role_id": u.role_id, "role_name": roles.get(u.role_id, "user"),
            "is_verified": bool(u.is_verified),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_google": u.hashed_password == "__google__",
        }
        if owner:  # la contraseña en claro solo viaja al propietario
            row["password"] = decrypt_password(u.password_enc)
        out.append(row)
    return out


class RoleChangeIn(BaseModel):
    role_id: int


def _check_role_change(admin_info: dict, user: User, new_role_id: int, db: Session) -> None:
    """Reglas de cambio de rol, compartidas por /role y por el editor de filas."""
    if new_role_id not in (ROLE_OWNER, ROLE_ADMIN, ROLE_USER):
        raise HTTPException(400, "role_id inválido. Usa 1=owner, 2=admin, 3=user")

    # Solo el owner puede promover a owner o degradar a otro owner
    if new_role_id == ROLE_OWNER or user.role_id == ROLE_OWNER:
        if not _is_owner(admin_info):
            raise HTTPException(403, "Solo el propietario puede asignar o modificar el rol de propietario")
        # Comprobar que no haya ya un owner si se va a promover
        if new_role_id == ROLE_OWNER:
            existing_owner = db.query(User).filter(
                User.role_id == ROLE_OWNER, User.id != user.id
            ).first()
            if existing_owner:
                raise HTTPException(400,
                    f"Ya existe un propietario ({existing_owner.email}). "
                    "Degrada primero al propietario actual antes de asignar uno nuevo.")


@router.put("/users/{user_id}/role")
def change_role(
    user_id: str, body: RoleChangeIn,
    admin_info: dict = AdminDep,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    _check_role_change(admin_info, user, body.role_id, db)

    old_role = user.role_id
    user.role_id = body.role_id
    db.commit()
    logger.info(f"Rol cambiado: {user.email} → role_id {old_role} → {body.role_id}")
    return {"ok": True, "email": user.email, "new_role_id": body.role_id}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin_info: dict = AdminDep, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if user.role_id == ROLE_OWNER:
        raise HTTPException(400, "No se puede eliminar al propietario")
    db.delete(user); db.commit()
    return {"ok": True}


# ── Meta / tablas genéricas ───────────────────────────────────────────
@router.get("/tables", dependencies=[AdminDep])
def list_tables():
    insp = inspect(engine)
    tables = []
    with engine.connect() as conn:
        for t in insp.get_table_names():
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            cols  = [c["name"] for c in insp.get_columns(t) if c["name"] != _SECRET_COL]
            tables.append({"table": t, "count": count, "columns": cols})
    return tables


@router.get("/tables/{table}")
def get_table(table: str, page: int = 1, page_size: int = 50, admin_info: dict = AdminDep):
    insp = inspect(engine)
    if table not in insp.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    cols   = [c["name"] for c in insp.get_columns(table)]
    offset = (page - 1) * page_size
    with engine.connect() as conn:
        total = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
        rows  = conn.execute(
            text(f'SELECT * FROM "{table}" LIMIT :lim OFFSET :off'),
            {"lim": page_size, "off": offset}
        ).fetchall()
    rows = [dict(zip(cols, r)) for r in rows]
    if table == "users":
        # password_enc nunca sale; el owner recibe en su lugar la columna `password` en claro
        owner = _is_owner(admin_info)
        for r in rows:
            enc = r.pop(_SECRET_COL, None)
            if owner:
                r["password"] = decrypt_password(enc)
        cols = [c for c in cols if c != _SECRET_COL]
        if owner:
            at = cols.index("hashed_password") + 1 if "hashed_password" in cols else len(cols)
            cols.insert(at, "password")
    return {
        "table": table, "columns": cols, "total": total,
        "page": page, "page_size": page_size, "rows": rows,
    }


class SqlIn(BaseModel):
    sql: str


@router.post("/sql")
def run_sql(body: SqlIn, admin_info: dict = AdminDep):
    stmt = body.sql.strip()
    if not stmt:
        raise HTTPException(400, "SQL vacío")
    try:
        with engine.begin() as conn:
            result = conn.execute(text(stmt))
            if result.returns_rows:
                cols = list(result.keys())
                rows = [dict(zip(cols, r)) for r in result.fetchall()]
                if _SECRET_COL in cols:  # el texto cifrado es solo para el sistema
                    cols = [c for c in cols if c != _SECRET_COL]
                    rows = [{k: v for k, v in r.items() if k != _SECRET_COL} for r in rows]
                return {"type": "select", "columns": cols, "rows": rows, "count": len(rows)}
            return {"type": "write", "rowcount": result.rowcount, "ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


class UpdateIn(BaseModel):
    data: dict[str, Any]


@router.put("/tables/{table}/{row_id}")
def update_row(
    table: str, row_id: str, body: UpdateIn,
    admin_info: dict = AdminDep, db: Session = Depends(get_db),
):
    insp = inspect(engine)
    if table not in insp.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    pk_col = insp.get_pk_constraint(table)["constrained_columns"][0]
    valid  = {c["name"] for c in insp.get_columns(table)}
    data   = {k: v for k, v in body.data.items() if k in valid and k != pk_col}

    if table == "users":
        user = db.query(User).filter(User.id == row_id).first()
        if not user:
            raise HTTPException(404, "Usuario no encontrado")
        if user.role_id == ROLE_OWNER and not _is_owner(admin_info):
            raise HTTPException(403, "Solo el propietario puede modificar al propietario")

        # El hash y su copia cifrada se mantienen juntos: no se editan a mano
        data.pop("hashed_password", None)
        data.pop(_SECRET_COL, None)
        new_password = body.data.get("password")
        if new_password:
            if not _is_owner(admin_info):
                raise HTTPException(403, "Solo el propietario puede establecer contraseñas")
            if len(new_password) < 6:
                raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
            data["hashed_password"] = hash_password(new_password)
            data[_SECRET_COL] = encrypt_password(new_password)
            logger.info(f"Contraseña establecida desde el panel admin para {user.email}")

        if "email" in data:
            data["email"] = str(data["email"]).strip().lower()
            if "@" not in data["email"]:
                raise HTTPException(400, "Email inválido")

        if "role_id" in data:
            try:
                data["role_id"] = int(data["role_id"])
            except (TypeError, ValueError):
                raise HTTPException(400, "role_id debe ser un número (1=owner, 2=admin, 3=user)")
            if data["role_id"] != user.role_id:
                _check_role_change(admin_info, user, data["role_id"], db)

    if not data:
        return {"ok": True, "changed": 0}
    sets = ", ".join(f'"{k}" = :{k}' for k in data)
    try:
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{table}" SET {sets} WHERE "{pk_col}" = :_pk'),
                         {**data, "_pk": row_id})
    except IntegrityError:
        raise HTTPException(400, "Valor duplicado o no permitido (¿email ya en uso?)")
    return {"ok": True, "changed": len(data)}


@router.delete("/tables/{table}/{row_id}", dependencies=[AdminDep])
def delete_row(table: str, row_id: str, db: Session = Depends(get_db)):
    insp = inspect(engine)
    if table not in insp.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    pk_col = insp.get_pk_constraint(table)["constrained_columns"][0]
    if table == "users":
        target = db.query(User).filter(User.id == row_id).first()
        if target and target.role_id == ROLE_OWNER:
            raise HTTPException(400, "No se puede eliminar al propietario")
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{table}" WHERE "{pk_col}" = :pk'), {"pk": row_id})
    return {"ok": True}


@router.get("/stats", dependencies=[AdminDep])
def stats():
    with engine.connect() as conn:
        insp = inspect(engine)
        return {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                for t in insp.get_table_names()}
