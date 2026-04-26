"""Endpoints de autenticacion completa.

Flujo de registro correcto:
  1. POST /register  → guarda registro PENDIENTE en memoria, envia email con codigo
  2. POST /verify-code → si codigo correcto, CREA el usuario en BD (la cuenta no existe antes)

Los registros pendientes expiran a los 15 min si no se verifican.
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import ROLE_USER, User, get_db
from app.services.auth_service import (
    create_token, get_current_user,
    hash_password, verify_password,
)
from app.services.email_service import send_reset_email, send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Registro pendiente (en memoria, expira 15 min) ────────────────────
_PENDING: dict[str, dict[str, Any]] = {}
_PENDING_TTL = 15 * 60   # 15 minutos


def _gen_code() -> str:
    import random
    return f"{random.randint(0, 999999):06d}"


def _clean_expired() -> None:
    now = time.time()
    expired = [e for e, p in _PENDING.items() if now - p["created_at"] > _PENDING_TTL]
    for e in expired:
        del _PENDING[e]


# ── Schemas ───────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: str
    password: str
    display_name: str = ""


class VerifyCodeIn(BaseModel):
    email: str
    code: str


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    token: str
    user_id: str
    email: str
    display_name: str
    is_verified: bool = False
    role: str = "user"


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    new_password: str


class GoogleIn(BaseModel):
    credential: str


# ── Register (guarda pendiente, NO crea usuario aun) ─────────────────
@router.post("/register", response_model=dict)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    _clean_expired()
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Email inválido")
    if len(body.password or "") < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")

    # Verificar que no existe ya una cuenta verificada con ese email
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "Ya existe una cuenta con ese email. Inicia sesión.")

    code = _gen_code()
    display = (body.display_name or "").strip() or email.split("@")[0]

    # Almacenar registro pendiente (sobrescribe si ya había uno anterior)
    _PENDING[email] = {
        "code":            code,
        "hashed_password": hash_password(body.password),
        "display_name":    display,
        "created_at":      time.time(),
    }

    email_sent = False
    try:
        from app.services.email_service import RESEND_API_KEY
        if RESEND_API_KEY:
            email_sent = send_verification_email(email, code, display)
    except Exception as e:
        logger.warning(f"Email no enviado: {e}")

    logger.info(f"Registro pendiente: {email} | email_sent={email_sent}")
    return {
        "message":    "Código enviado. Introdúcelo para crear tu cuenta.",
        "email_sent": email_sent,
        "dev_code":   code if not email_sent else None,  # solo en modo dev
    }


# ── Verify code (crea el usuario si el codigo es correcto) ───────────
@router.post("/verify-code", response_model=dict)
def verify_code(body: VerifyCodeIn, db: Session = Depends(get_db)):
    _clean_expired()
    email = (body.email or "").strip().lower()
    code  = (body.code  or "").strip()

    pending = _PENDING.get(email)
    if not pending:
        raise HTTPException(
            400,
            "No hay ningún registro pendiente para ese email o el código ha expirado (15 min). "
            "Por favor, vuelve a registrarte."
        )

    if time.time() - pending["created_at"] > _PENDING_TTL:
        del _PENDING[email]
        raise HTTPException(400, "El código ha expirado. Vuelve a registrarte.")

    if pending["code"] != code:
        raise HTTPException(400, "Código incorrecto. Inténtalo de nuevo.")

    # Código correcto → crear el usuario ahora
    # Doble-check por si alguien se registró en otro dispositivo mientras tanto
    if db.query(User).filter(User.email == email).first():
        del _PENDING[email]
        raise HTTPException(400, "Ya existe una cuenta con ese email. Inicia sesión.")

    user = User(
        email=email,
        display_name=pending["display_name"],
        hashed_password=pending["hashed_password"],
        is_verified=1,          # verificado desde el primer momento
        role_id=ROLE_USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    del _PENDING[email]

    logger.info(f"Usuario creado tras verificación: {email}")
    return {
        "token":        create_token(user.id, user.email),
        "user_id":      user.id,
        "email":        user.email,
        "display_name": user.display_name,
        "is_verified":  True,
        "role":         "user",
    }


# ── Login ─────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Email o contraseña incorrectos")
    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email,
        display_name=user.display_name,
        is_verified=bool(user.is_verified),
        role=user.role_name,
    )


# ── Password recovery ─────────────────────────────────────────────────
@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token     = token
        user.reset_token_exp = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        send_reset_email(user.email, token, user.display_name)
    return {"message": "Si existe una cuenta con ese email, recibirás un enlace de recuperación."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == body.token).first()
    if not user:
        raise HTTPException(400, "Token inválido o expirado")
    if user.reset_token_exp and datetime.utcnow() > user.reset_token_exp:
        raise HTTPException(400, "El enlace de recuperación ha expirado")
    if len(body.new_password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    user.hashed_password = hash_password(body.new_password)
    user.reset_token     = None
    user.reset_token_exp = None
    db.commit()
    return {"message": "Contraseña restablecida correctamente"}


# ── Google OAuth ──────────────────────────────────────────────────────
@router.post("/google", response_model=TokenOut)
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(501, "Google OAuth no está configurado en este servidor")
    try:
        from google.oauth2 import id_token as gid
        from google.auth.transport import requests as greq
        info = gid.verify_oauth2_token(body.credential, greq.Request(), client_id)
    except Exception as e:
        raise HTTPException(401, f"Token de Google inválido: {e}")

    email = info.get("email", "").lower()
    name  = info.get("name") or info.get("given_name") or email.split("@")[0]
    if not email:
        raise HTTPException(400, "No se pudo obtener el email de Google")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, display_name=name,
                    hashed_password="__google__", is_verified=1, role_id=ROLE_USER)
        db.add(user); db.commit(); db.refresh(user)

    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email,
        display_name=user.display_name, is_verified=True, role=user.role_name,
    )


# ── Me ────────────────────────────────────────────────────────────────
@router.get("/me")
def me(user: User | None = Depends(get_current_user)):
    if not user:
        return {"authenticated": False, "role": "guest"}
    return {
        "authenticated": True, "user_id": user.id,
        "email": user.email, "display_name": user.display_name,
        "is_verified": bool(user.is_verified), "role": user.role_name,
    }
