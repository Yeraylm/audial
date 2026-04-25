"""Panel de administración de base de datos.

Acceso protegido por ADMIN_SECRET (variable de entorno).
Expone endpoints CRUD + SQL para todas las tablas.
Solo debe conocer la URL y la clave el propietario/admin del sistema.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models.database import get_db, engine

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "audial-admin-2026")


# ── Auth ─────────────────────────────────────────────────────────────
def _require_admin(x_admin_token: str | None = Header(None, alias="X-Admin-Token")):
    if not x_admin_token or x_admin_token != ADMIN_SECRET:
        raise HTTPException(403, "Acceso denegado. Token de administrador incorrecto.")


class AuthIn(BaseModel):
    secret: str

@router.post("/auth")
def admin_auth(body: AuthIn):
    if body.secret != ADMIN_SECRET:
        raise HTTPException(403, "Clave de administrador incorrecta")
    return {"token": ADMIN_SECRET, "ok": True}


# ── Meta ──────────────────────────────────────────────────────────────
@router.get("/tables", dependencies=[Depends(_require_admin)])
def list_tables():
    inspector = inspect(engine)
    tables = []
    with engine.connect() as conn:
        for t in inspector.get_table_names():
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            cols  = [c["name"] for c in inspector.get_columns(t)]
            tables.append({"table": t, "count": count, "columns": cols})
    return tables


@router.get("/tables/{table}", dependencies=[Depends(_require_admin)])
def get_table(table: str, page: int = 1, page_size: int = 50):
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    cols = [c["name"] for c in inspector.get_columns(table)]
    offset = (page - 1) * page_size
    with engine.connect() as conn:
        total  = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
        rows   = conn.execute(
            text(f'SELECT * FROM "{table}" LIMIT :limit OFFSET :offset'),
            {"limit": page_size, "offset": offset}
        ).fetchall()
    return {
        "table": table, "columns": cols, "total": total,
        "page": page, "page_size": page_size,
        "rows": [dict(zip(cols, r)) for r in rows],
    }


# ── SQL ───────────────────────────────────────────────────────────────
class SqlIn(BaseModel):
    sql: str

@router.post("/sql", dependencies=[Depends(_require_admin)])
def run_sql(body: SqlIn):
    stmt = body.sql.strip()
    if not stmt:
        raise HTTPException(400, "SQL vacío")
    try:
        with engine.begin() as conn:
            result = conn.execute(text(stmt))
            # SELECT
            if result.returns_rows:
                cols = list(result.keys())
                rows = [dict(zip(cols, r)) for r in result.fetchall()]
                return {"type": "select", "columns": cols, "rows": rows, "count": len(rows)}
            # INSERT / UPDATE / DELETE
            return {"type": "write", "rowcount": result.rowcount, "ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))


# ── CRUD genérico ─────────────────────────────────────────────────────
class UpdateIn(BaseModel):
    data: dict[str, Any]

@router.put("/tables/{table}/{row_id}", dependencies=[Depends(_require_admin)])
def update_row(table: str, row_id: str, body: UpdateIn, db: Session = Depends(get_db)):
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    pk = inspector.get_pk_constraint(table)["constrained_columns"]
    if not pk:
        raise HTTPException(400, "Tabla sin clave primaria")
    pk_col = pk[0]
    sets = ", ".join(f'"{k}" = :{k}' for k in body.data)
    params = {**body.data, "_pk": row_id}
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE "{table}" SET {sets} WHERE "{pk_col}" = :_pk'), params)
    return {"ok": True}


@router.delete("/tables/{table}/{row_id}", dependencies=[Depends(_require_admin)])
def delete_row(table: str, row_id: str):
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        raise HTTPException(404, f"Tabla '{table}' no existe")
    pk = inspector.get_pk_constraint(table)["constrained_columns"]
    if not pk:
        raise HTTPException(400, "Tabla sin clave primaria")
    pk_col = pk[0]
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{table}" WHERE "{pk_col}" = :pk'), {"pk": row_id})
    return {"ok": True}


@router.get("/stats", dependencies=[Depends(_require_admin)])
def stats():
    with engine.connect() as conn:
        inspector = inspect(engine)
        result = {}
        for t in inspector.get_table_names():
            result[t] = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
    return result
