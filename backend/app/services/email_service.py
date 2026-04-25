"""Servicio de email via Resend API (gratis, sin servidor SMTP).

Configuracion:
  RESEND_API_KEY = re_xxxx    → clave de https://resend.com (gratis, 3000 emails/mes)
  APP_URL        = https://audial.netlify.app  → URL del frontend

Sin RESEND_API_KEY los emails se loguean en consola (modo dev).
"""
from __future__ import annotations

import os

import httpx
from loguru import logger

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
APP_URL        = os.getenv("APP_URL", "https://audial.netlify.app")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "Audial <onboarding@resend.dev>")


def send_email(to: str, subject: str, html: str) -> bool:
    """Envía un email via Resend. Devuelve True si OK."""
    if not RESEND_API_KEY:
        logger.warning(f"[EMAIL DEV] To:{to} | Subject:{subject}\n(RESEND_API_KEY no configurada)")
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=15,
        )
        if r.status_code not in (200, 201):
            logger.error(f"Resend error {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False


def send_verification_email(to: str, token: str, name: str = "") -> bool:
    url   = f"{APP_URL}/api/auth/verify/{token}"
    greeting = f"Hola {name}," if name else "Hola,"
    html  = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        <h1 style="color:#F5A623;font-size:28px;margin:0">🎙 Audial</h1>
      </div>
      <h2 style="color:#F4EFE8">{greeting}</h2>
      <p style="color:#AEA290">Gracias por registrarte en Audial. Verifica tu email para activar tu cuenta:</p>
      <div style="text-align:center;margin:32px 0">
        <a href="{url}"
           style="background:linear-gradient(135deg,#F5A623,#E85A4F);color:white;
                  padding:14px 28px;border-radius:999px;text-decoration:none;
                  font-weight:700;font-size:16px">
          Verificar email
        </a>
      </div>
      <p style="color:#66596e;font-size:12px">Este enlace caduca en 24 horas.<br>
         Si no creaste esta cuenta, ignora este mensaje.</p>
      <hr style="border-color:#221f33;margin:24px 0">
      <p style="color:#66596e;font-size:12px;text-align:center">
        Audial · Plataforma IA Conversacional
      </p>
    </div>
    """
    return send_email(to, "Verifica tu cuenta en Audial", html)


def send_reset_email(to: str, token: str, name: str = "") -> bool:
    url     = f"{APP_URL}?reset_token={token}"
    greeting = f"Hola {name}," if name else "Hola,"
    html    = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        <h1 style="color:#F5A623;font-size:28px;margin:0">🎙 Audial</h1>
      </div>
      <h2 style="color:#F4EFE8">{greeting}</h2>
      <p style="color:#AEA290">Recibimos una solicitud para restablecer tu contraseña.</p>
      <div style="text-align:center;margin:32px 0">
        <a href="{url}"
           style="background:linear-gradient(135deg,#F5A623,#E85A4F);color:white;
                  padding:14px 28px;border-radius:999px;text-decoration:none;
                  font-weight:700;font-size:16px">
          Restablecer contraseña
        </a>
      </div>
      <p style="color:#66596e;font-size:12px">Este enlace caduca en 1 hora.<br>
         Si no solicitaste esto, ignora este mensaje.</p>
      <hr style="border-color:#221f33;margin:24px 0">
      <p style="color:#66596e;font-size:12px;text-align:center">
        Audial · Plataforma IA Conversacional
      </p>
    </div>
    """
    return send_email(to, "Restablece tu contraseña en Audial", html)
