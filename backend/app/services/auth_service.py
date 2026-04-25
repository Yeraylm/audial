"""Servicio de autenticación: JWT + bcrypt."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.database import User, get_db

SECRET_KEY  = os.getenv("JWT_SECRET", "audial-tfm-secret-2026-x7k2p")
ALGORITHM   = "HS256"
EXPIRE_DAYS = 30

pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer   = HTTPBearer(auto_error=False)


# ── password ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────────────
def create_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(days=EXPIRE_DAYS)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {e}")


# ── dependency ────────────────────────────────────────────────────────
def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Devuelve el User si hay token válido.
    Devuelve None si no hay token (modo invitado con session_id).
    Lanza 401 si el token existe pero es inválido.
    """
    if not creds:
        return None
    payload = decode_token(creds.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sin subject")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")
    return user

def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Como get_current_user pero lanza 401 si no hay token."""
    user = get_current_user(creds, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticación requerida")
    return user
