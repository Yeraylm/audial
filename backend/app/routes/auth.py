"""Endpoints de autenticación: registro, login, perfil, Google OAuth."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import User, get_db
from app.services.auth_service import (
    create_token, get_current_user,
    hash_password, verify_password,
)

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


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(400, "Ya existe una cuenta con ese email")
    if len(body.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    user = User(
        email=body.email.lower(),
        display_name=body.display_name or body.email.split("@")[0],
        hashed_password=hash_password(body.password),
    )
    db.add(user); db.commit(); db.refresh(user)
    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email, display_name=user.display_name,
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Email o contraseña incorrectos")
    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email, display_name=user.display_name,
    )


class GoogleIn(BaseModel):
    credential: str  # Google ID token


@router.post("/google", response_model=TokenOut)
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    """Verifica el token de Google y crea/encuentra la cuenta."""
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
    name  = info.get("name", "") or info.get("given_name", "") or email.split("@")[0]
    if not email:
        raise HTTPException(400, "No se pudo obtener el email de Google")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, display_name=name, hashed_password="__google__")
        db.add(user); db.commit(); db.refresh(user)

    return TokenOut(
        token=create_token(user.id, user.email),
        user_id=user.id, email=user.email, display_name=user.display_name,
    )


@router.get("/me")
def me(user: User | None = Depends(get_current_user)):
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }
