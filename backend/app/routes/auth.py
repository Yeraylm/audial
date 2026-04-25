"""Endpoints de autenticación completa:
registro (+ verificación email) · login · Google OAuth ·
recuperar contraseña · restablecer contraseña · perfil.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import User, get_db
from app.services.auth_service import (
    create_token, get_current_user,
    hash_password, verify_password,
)
from app.services.email_service import send_reset_email, send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    password: str
    display_name: str = ""

class LoginIn(BaseModel):
    email: str
    password: str

class TokenOut(BaseModel):
    token: str
    user_id: str
    email: str
    display_name: str
    is_verified: bool = False

class ForgotIn(BaseModel):
    email: str

class ResetIn(BaseModel):
    token: str
    new_password: str

class GoogleIn(BaseModel):
    credential: str


def _new_token() -> str:
    return secrets.token_urlsafe(32)


@router.post("/register", response_model=dict)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    try:
        email = (body.email or "").strip().lower()
        if not email or "@" not in email:
            raise HTTPException(400, "Email inválido")
        if len(body.password or "") < 6:
            raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(400, "Ya existe una cuenta con ese email")

        ver_token = _new_token()
        user = User(
            email=email,
            display_name=(body.display_name or "").strip() or email.split("@")[0],
            hashed_password=hash_password(body.password),
            is_verified=0,
            verification_token=ver_token,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        email_sent = False
        try:
            email_sent = send_verification_email(email, ver_token, user.display_name)
        except Exception as email_err:
            logger.warning(f"Email no enviado: {email_err}")

        return {
            "message": "Cuenta creada.",
            "email_sent": email_sent,
            "user_id": user.id,
            "token": create_token(user.id, user.email) if not email_sent else None,
            "email": user.email,
            "display_name": user.display_name,
            "is_verified": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error en register: {e}")
        raise HTTPException(500, f"Error interno al registrar: {str(e)}")


@router.get("/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(400, "Token de verificación inválido o ya usado")
    user.is_verified = 1
    user.verification_token = None
    db.commit()
    # Redirigir al frontend con token de login
    from fastapi.responses import RedirectResponse
    auth_token = create_token(user.id, user.email)
    return RedirectResponse(
        url=f"{os.getenv('APP_URL', 'https://audial.netlify.app')}?verified=1&token={auth_token}"
    )


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
    )


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    # No revelar si el email existe o no
    if user:
        token = _new_token()
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


@router.post("/google", response_model=TokenOut)
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(501, "Google OAuth no está configurado en este servidor")
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        info = google_id_token.verify_oauth2_token(
            body.credential, google_requests.Request(), client_id
        )
    except Exception as e:
        raise HTTPException(401, f"Token de Google inválido: {e}")

    email = info.get("email", "").lower()
    name  = info.get("name") or info.get("given_name") or email.split("@")[0]
    if not email:
        raise HTTPException(400, "No se pudo obtener el email de Google")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, display_name=name, hashed_password="__google__", is_verified=1)
        db.add(user); db.commit(); db.refresh(user)

    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email,
        display_name=user.display_name, is_verified=True,
    )


@router.get("/me")
def me(user: User | None = Depends(get_current_user)):
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True, "user_id": user.id,
        "email": user.email, "display_name": user.display_name,
        "is_verified": bool(user.is_verified),
    }
