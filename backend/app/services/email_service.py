"""Servicio de email via Resend API."""
from __future__ import annotations

import os
import httpx
from loguru import logger

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
APP_URL        = os.getenv("APP_URL", "https://audial-wheat.vercel.app")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "Audial <onboarding@resend.dev>")


def send_email(to: str, subject: str, html: str) -> bool:
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


# ── Templates ────────────────────────────────────────────────────────
def _base_template(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Audial</title>
</head>
<body style="margin:0;padding:0;background:#050a05;font-family:'Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#050a05;min-height:100vh;padding:40px 16px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;">

        <!-- Header / Logo -->
        <tr><td style="padding-bottom:28px;text-align:center;">
          <table cellpadding="0" cellspacing="0" align="center">
            <tr>
              <td style="background:linear-gradient(135deg,rgba(57,255,20,.12),rgba(0,229,204,.08));
                         border:1px solid rgba(57,255,20,.25);border-radius:14px;
                         padding:12px 20px;">
                <span style="font-size:28px;font-weight:900;
                  background:linear-gradient(135deg,#39FF14,#00E5CC);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                  background-clip:text;letter-spacing:-0.5px;">
                  🎙 Audial
                </span>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Card -->
        <tr><td style="background:linear-gradient(135deg,rgba(255,255,255,.05),rgba(255,255,255,.02));
                       border:1px solid rgba(57,255,20,.12);border-radius:20px;
                       padding:40px 36px;box-shadow:0 24px 60px rgba(0,0,0,.5);">
          {content}
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding-top:28px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#4A654A;line-height:1.6;">
            Plataforma IA Conversacional · Procesamiento 100% local<br/>
            <a href="{APP_URL}" style="color:#39FF14;text-decoration:none;">{APP_URL}</a>
          </p>
          <p style="margin:8px 0 0;font-size:11px;color:#2d3d2d;">
            Si no creaste esta cuenta, ignora este mensaje.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_verification_email(to: str, code: str, name: str = "") -> bool:
    greeting = f"Hola, <strong style='color:#E8F5E8'>{name}</strong> 👋" if name else "Hola 👋"
    content = f"""
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#E8F5E8;letter-spacing:-0.5px;">
        Verifica tu cuenta
      </h1>
      <p style="margin:0 0 28px;font-size:15px;color:#8DA88D;line-height:1.6;">
        {greeting} Usa el siguiente código para completar tu registro en Audial.
      </p>

      <!-- Code box -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr><td style="background:rgba(57,255,20,.06);border:2px solid rgba(57,255,20,.3);
                       border-radius:14px;padding:28px 20px;text-align:center;">
          <p style="margin:0 0 10px;font-size:12px;text-transform:uppercase;
                    letter-spacing:.15em;color:#39FF14;font-weight:700;">
            Código de verificación
          </p>
          <p style="margin:0;font-size:52px;font-weight:900;letter-spacing:18px;
                    color:#39FF14;font-family:'Courier New',monospace;
                    text-shadow:0 0 30px rgba(57,255,20,.4);">
            {code}
          </p>
        </td></tr>
      </table>

      <!-- Steps -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr>
          <td width="28" valign="top" style="padding-top:2px;">
            <div style="width:22px;height:22px;background:rgba(57,255,20,.1);
                        border:1px solid rgba(57,255,20,.25);border-radius:50%;
                        text-align:center;line-height:22px;font-size:11px;font-weight:700;color:#39FF14;">1</div>
          </td>
          <td style="padding-left:10px;font-size:14px;color:#8DA88D;">
            Vuelve a la página de registro de Audial
          </td>
        </tr>
        <tr><td colspan="2" style="height:10px;"></td></tr>
        <tr>
          <td width="28" valign="top" style="padding-top:2px;">
            <div style="width:22px;height:22px;background:rgba(57,255,20,.1);
                        border:1px solid rgba(57,255,20,.25);border-radius:50%;
                        text-align:center;line-height:22px;font-size:11px;font-weight:700;color:#39FF14;">2</div>
          </td>
          <td style="padding-left:10px;font-size:14px;color:#8DA88D;">
            Introduce el código de 6 dígitos mostrado arriba
          </td>
        </tr>
        <tr><td colspan="2" style="height:10px;"></td></tr>
        <tr>
          <td width="28" valign="top" style="padding-top:2px;">
            <div style="width:22px;height:22px;background:rgba(57,255,20,.1);
                        border:1px solid rgba(57,255,20,.25);border-radius:50%;
                        text-align:center;line-height:22px;font-size:11px;font-weight:700;color:#39FF14;">3</div>
          </td>
          <td style="padding-left:10px;font-size:14px;color:#8DA88D;">
            ¡Listo! Tu cuenta quedará activada
          </td>
        </tr>
      </table>

      <p style="margin:0;font-size:12px;color:#4A654A;border-top:1px solid rgba(57,255,20,.08);
                padding-top:20px;line-height:1.6;">
        ⏱ Este código caduca en <strong style="color:#8DA88D;">15 minutos</strong>.
      </p>
    """
    return send_email(to, "🔑 Tu código de verificación · Audial", _base_template(content))


def send_reset_email(to: str, token: str, name: str = "") -> bool:
    url     = f"{APP_URL}?reset_token={token}"
    greeting = f"Hola, <strong style='color:#E8F5E8'>{name}</strong>" if name else "Hola"
    content = f"""
      <h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:#E8F5E8;letter-spacing:-0.5px;">
        Restablece tu contraseña
      </h1>
      <p style="margin:0 0 28px;font-size:15px;color:#8DA88D;line-height:1.6;">
        {greeting}, recibimos una solicitud para restablecer la contraseña de tu cuenta.
      </p>

      <!-- CTA Button -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr><td align="center">
          <a href="{url}" style="display:inline-block;background:linear-gradient(135deg,#39FF14,#00E5CC);
                                  color:#050a05;text-decoration:none;font-weight:800;font-size:15px;
                                  padding:14px 36px;border-radius:999px;
                                  box-shadow:0 8px 28px rgba(57,255,20,.3);">
            Restablecer contraseña →
          </a>
        </td></tr>
      </table>

      <p style="margin:0 0 16px;font-size:13px;color:#4A654A;line-height:1.6;">
        O copia y pega este enlace en tu navegador:
      </p>
      <div style="background:rgba(57,255,20,.04);border:1px solid rgba(57,255,20,.15);
                  border-radius:8px;padding:12px 14px;word-break:break-all;">
        <a href="{url}" style="color:#39FF14;font-size:12px;font-family:monospace;text-decoration:none;">{url}</a>
      </div>

      <p style="margin:20px 0 0;font-size:12px;color:#4A654A;border-top:1px solid rgba(57,255,20,.08);
                padding-top:20px;line-height:1.6;">
        ⏱ Este enlace caduca en <strong style="color:#8DA88D;">1 hora</strong>.
        Si no solicitaste este cambio, puedes ignorar este mensaje.
      </p>
    """
    return send_email(to, "🔒 Restablece tu contraseña · Audial", _base_template(content))
