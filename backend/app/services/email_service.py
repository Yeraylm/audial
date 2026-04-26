"""Servicio de email via Resend API.

Los templates usan HTML de email estándar (tablas, inline styles, bgcolor)
compatible con Gmail, Outlook y Apple Mail. Sin gradientes CSS ni variables.
"""
from __future__ import annotations

import os
import httpx
from loguru import logger

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
APP_URL        = os.getenv("APP_URL", "https://audial-wheat.vercel.app")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "Audial <onboarding@resend.dev>")

# Colores de marca
C_BG       = "#0a0f0a"
C_CARD     = "#111811"
C_CARD2    = "#182418"
C_GREEN    = "#39FF14"
C_CYAN     = "#00E5CC"
C_TEXT     = "#E8F5E8"
C_MUTED    = "#6B8F6B"
C_BORDER   = "#1e2e1e"
C_CODE_BG  = "#0d1a0d"


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


def _wrap(body: str, preheader: str = "") -> str:
    """Plantilla base: fondo oscuro, header con logo, footer. Compatible Gmail/Outlook."""
    pre = f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;</div>' if preheader else ""
    return f"""<!DOCTYPE html>
<html lang="es" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta name="x-apple-disable-message-reformatting"/>
  <title>Audial</title>
  <!--[if mso]>
  <noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
  <![endif]-->
  <style>
    body {{ margin:0; padding:0; background-color:{C_BG}; -webkit-text-size-adjust:100%; }}
    table {{ border-spacing:0; }}
    td {{ padding:0; }}
    img {{ border:0; }}
    .btn:hover {{ opacity:0.85 !important; }}
    @media screen and (max-width:600px) {{
      .email-wrap {{ width:100% !important; }}
      .btn {{ width:100% !important; display:block !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:{C_BG};">
{pre}

<!-- Email wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="{C_BG}" style="background-color:{C_BG};min-height:100vh;">
  <tr><td align="center" style="padding:40px 16px;">

    <!-- Content card -->
    <table class="email-wrap" width="560" cellpadding="0" cellspacing="0"
           style="max-width:560px;width:100%;">

      <!-- TOP ACCENT BAR -->
      <tr>
        <td height="4" bgcolor="{C_GREEN}" style="background-color:{C_GREEN};font-size:0;line-height:0;border-radius:4px 4px 0 0;">&nbsp;</td>
      </tr>

      <!-- HEADER / LOGO -->
      <tr>
        <td bgcolor="{C_CARD}" style="background-color:{C_CARD};padding:32px 40px 24px;
            border-left:1px solid {C_BORDER};border-right:1px solid {C_BORDER};">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <table cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="background-color:{C_CODE_BG};border:1px solid #1e3a1e;
                                border-radius:10px;padding:8px 14px;">
                      <span style="font-size:22px;">🎙</span>
                      <span style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                                   font-size:22px;font-weight:900;color:{C_GREEN};
                                   letter-spacing:-0.5px;vertical-align:middle;">
                        Audial
                      </span>
                    </td>
                  </tr>
                </table>
              </td>
              <td align="right">
                <span style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                             font-size:12px;color:{C_MUTED};letter-spacing:.08em;text-transform:uppercase;">
                  Plataforma IA Conversacional
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- DIVIDER -->
      <tr>
        <td height="1" bgcolor="{C_BORDER}" style="background-color:{C_BORDER};font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <!-- BODY -->
      <tr>
        <td bgcolor="{C_CARD}" style="background-color:{C_CARD};padding:32px 40px;
            border-left:1px solid {C_BORDER};border-right:1px solid {C_BORDER};">
          {body}
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td bgcolor="{C_CARD2}" style="background-color:{C_CARD2};padding:20px 40px;
            border-left:1px solid {C_BORDER};border-right:1px solid {C_BORDER};
            border-bottom:1px solid {C_BORDER};border-radius:0 0 12px 12px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="center">
                <p style="margin:0 0 6px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                          font-size:12px;color:{C_MUTED};line-height:1.6;">
                  Audial &middot; Plataforma IA Conversacional &middot; 100% Local
                </p>
                <p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                          font-size:12px;color:{C_MUTED};">
                  <a href="{APP_URL}" style="color:{C_GREEN};text-decoration:none;">{APP_URL}</a>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
    <!-- /Content card -->

  </td></tr>
</table>
<!-- /Email wrapper -->

</body>
</html>"""


def send_verification_email(to: str, code: str, name: str = "") -> bool:
    greeting = f"Hola, <strong style='color:{C_TEXT};'>{name}</strong> 👋" if name else "Hola 👋"
    digits = "".join(
        f'<td width="46" height="60" align="center" bgcolor="{C_CODE_BG}" '
        f'style="background-color:{C_CODE_BG};border:1px solid {C_GREEN};border-radius:8px;'
        f'font-family:Courier New,Courier,monospace;font-size:30px;font-weight:900;'
        f'color:{C_GREEN};">{d}</td>'
        for d in code
    )
    body = f"""
      <!-- Greeting -->
      <p style="margin:0 0 6px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:28px;font-weight:800;color:{C_TEXT};letter-spacing:-0.5px;">
        Verifica tu cuenta
      </p>
      <p style="margin:0 0 28px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:15px;color:{C_MUTED};line-height:1.6;">
        {greeting} &mdash; Usa este código para activar tu cuenta de Audial.
        <br/>Caduca en <strong style="color:{C_TEXT};">15 minutos</strong>.
      </p>

      <!-- Code box label -->
      <p style="margin:0 0 10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:11px;font-weight:700;color:{C_GREEN};text-transform:uppercase;
                letter-spacing:.2em;">
        Código de verificación
      </p>

      <!-- Code digits -->
      <table cellpadding="0" cellspacing="6" style="margin-bottom:28px;">
        <tr>{digits}</tr>
      </table>

      <!-- Divider -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr><td height="1" bgcolor="{C_BORDER}" style="background-color:{C_BORDER};font-size:0;">&nbsp;</td></tr>
      </table>

      <!-- Steps -->
      <p style="margin:0 0 14px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:13px;font-weight:700;color:{C_TEXT};text-transform:uppercase;
                letter-spacing:.08em;">
        Cómo usar el código
      </p>
      <table cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td width="28" valign="top">
            <table cellpadding="0" cellspacing="0">
              <tr><td width="22" height="22" align="center" bgcolor="{C_CODE_BG}"
                style="background-color:{C_CODE_BG};border:1px solid {C_BORDER};border-radius:50%;
                       font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                       font-size:12px;font-weight:700;color:{C_GREEN};">1</td></tr>
            </table>
          </td>
          <td style="padding-left:10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                     font-size:14px;color:{C_MUTED};line-height:1.5;padding-bottom:10px;">
            Vuelve a la página de registro de Audial
          </td>
        </tr>
        <tr>
          <td width="28" valign="top">
            <table cellpadding="0" cellspacing="0">
              <tr><td width="22" height="22" align="center" bgcolor="{C_CODE_BG}"
                style="background-color:{C_CODE_BG};border:1px solid {C_BORDER};border-radius:50%;
                       font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                       font-size:12px;font-weight:700;color:{C_GREEN};">2</td></tr>
            </table>
          </td>
          <td style="padding-left:10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                     font-size:14px;color:{C_MUTED};line-height:1.5;padding-bottom:10px;">
            Introduce los 6 dígitos en el campo de verificación
          </td>
        </tr>
        <tr>
          <td width="28" valign="top">
            <table cellpadding="0" cellspacing="0">
              <tr><td width="22" height="22" align="center" bgcolor="{C_CODE_BG}"
                style="background-color:{C_CODE_BG};border:1px solid {C_BORDER};border-radius:50%;
                       font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                       font-size:12px;font-weight:700;color:{C_GREEN};">3</td></tr>
            </table>
          </td>
          <td style="padding-left:10px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                     font-size:14px;color:{C_MUTED};line-height:1.5;">
            ¡Tu cuenta quedará activada y podrás iniciar sesión!
          </td>
        </tr>
      </table>

      <!-- Security note -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
        <tr>
          <td bgcolor="{C_CODE_BG}" style="background-color:{C_CODE_BG};border-left:3px solid {C_GREEN};
              border-radius:0 6px 6px 0;padding:12px 16px;">
            <p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                      font-size:12px;color:{C_MUTED};line-height:1.6;">
              🔒 <strong style="color:{C_TEXT};">Nota de seguridad:</strong>
              Si no has creado esta cuenta en Audial, ignora este mensaje.
              Nadie te pedirá este código por teléfono ni por ningún otro medio.
            </p>
          </td>
        </tr>
      </table>
    """
    return send_email(
        to,
        f"🔑 {code} — Tu código de verificación · Audial",
        _wrap(body, preheader=f"Tu código de verificación de Audial es: {code}")
    )


def send_reset_email(to: str, token: str, name: str = "") -> bool:
    url      = f"{APP_URL}?reset_token={token}"
    greeting = f"Hola, <strong style='color:{C_TEXT};'>{name}</strong>" if name else "Hola"
    body = f"""
      <p style="margin:0 0 6px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:28px;font-weight:800;color:{C_TEXT};letter-spacing:-0.5px;">
        Restablece tu contraseña
      </p>
      <p style="margin:0 0 28px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:15px;color:{C_MUTED};line-height:1.6;">
        {greeting} &mdash; Recibimos una solicitud para restablecer la contraseña de tu cuenta.
        El enlace caduca en <strong style="color:{C_TEXT};">1 hora</strong>.
      </p>

      <!-- CTA Button -->
      <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr>
          <td align="center" bgcolor="{C_GREEN}" class="btn"
            style="background-color:{C_GREEN};border-radius:999px;padding:14px 36px;">
            <a href="{url}" class="btn"
               style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                      font-size:15px;font-weight:800;color:#050a05;text-decoration:none;
                      display:inline-block;">
              Restablecer contraseña &rarr;
            </a>
          </td>
        </tr>
      </table>

      <!-- URL fallback -->
      <p style="margin:0 0 8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                font-size:12px;color:{C_MUTED};">
        O copia y pega este enlace en tu navegador:
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr>
          <td bgcolor="{C_CODE_BG}" style="background-color:{C_CODE_BG};border:1px solid {C_BORDER};
              border-radius:8px;padding:10px 14px;word-break:break-all;">
            <a href="{url}" style="font-family:Courier New,Courier,monospace;font-size:12px;
                                   color:{C_CYAN};text-decoration:none;">{url}</a>
          </td>
        </tr>
      </table>

      <!-- Security note -->
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td bgcolor="{C_CODE_BG}" style="background-color:{C_CODE_BG};border-left:3px solid {C_CYAN};
              border-radius:0 6px 6px 0;padding:12px 16px;">
            <p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
                      font-size:12px;color:{C_MUTED};line-height:1.6;">
              🔒 Si no solicitaste este cambio, puedes ignorar este mensaje.
              Tu contraseña actual no se modificará.
            </p>
          </td>
        </tr>
      </table>
    """
    return send_email(
        to,
        "🔒 Restablece tu contraseña · Audial",
        _wrap(body, preheader="Solicitud de restablecimiento de contraseña de Audial")
    )
