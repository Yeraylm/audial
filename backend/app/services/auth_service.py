"""Autenticacion sin dependencias externas.

Usa solo libreria estandar de Python:
  - hashlib + secrets  → hash de contrasenas (SHA-256 + salt aleatorio)
  - hmac + base64      → tokens JWT-like firmados con HMAC-SHA256

No requiere passlib, jose ni cryptography.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy.orm import Session

from app.models.database import User, get_db

_SECRET = os.getenv("JWT_SECRET", "audial-tfm-secret-2026-change-in-production")
_EXPIRE_SECONDS = 30 * 24 * 3600  # 30 días

bearer = HTTPBearer(auto_error=False)


# ── Password hashing (SHA-256 + random salt) ──────────────────────────
def hash_password(plain: str) -> str:
    """Devuelve 'salt$sha256hex'. Seguro contra ataques de diccionario."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{plain}{salt}{_SECRET}".encode()).hexdigest()
    return f"{salt}${digest}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        expected = hashlib.sha256(f"{plain}{salt}{_SECRET}".encode()).hexdigest()
        return hmac.compare_digest(expected, digest)
    except Exception:
        return False


# ── Token (HMAC-SHA256 firmado) ───────────────────────────────────────
def create_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": int(time.time()) + _EXPIRE_SECONDS}
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig  = hmac.new(_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        data, sig = token.rsplit(".", 1)
        expected  = hmac.new(_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("Firma inválida")
        padding = 4 - len(data) % 4
        payload = json.loads(base64.urlsafe_b64decode(data + "=" * padding))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expirado")
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")


# ── FastAPI dependencies ──────────────────────────────────────────────
def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if not creds:
        return None
    payload = decode_token(creds.credentials)
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")
    return user


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(creds, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticación requerida")
    return user
