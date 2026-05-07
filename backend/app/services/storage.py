"""Supabase Storage — persistencia de archivos de audio en la nube.

Si SUPABASE_URL y SUPABASE_SERVICE_KEY están configurados, los archivos
de audio se suben automáticamente al bucket 'audio-files' (público).
Cuando el contenedor de HF Spaces se reinicia y borra el disco local,
el endpoint /api/audio/{id}/file redirige a la URL de Supabase Storage
para que el reproductor siga funcionando.

Sin estas variables, el servicio queda deshabilitado silenciosamente.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.core.config import settings

_BUCKET = "audio-files"


def _headers() -> dict[str, str]:
    key = (settings.supabase_service_key or "").strip()
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }


def _http_put(url: str, headers: dict, data: bytes) -> int:
    """PUT bytes to URL; returns HTTP status code. Tries httpx then urllib."""
    try:
        import httpx  # noqa: PLC0415  (httpx es dep transitiva de groq)
        r = httpx.put(url, headers=headers, content=data, timeout=120)
        return r.status_code
    except ImportError:
        pass
    try:
        import urllib.request  # noqa: PLC0415
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.getcode()
    except Exception as e:
        logger.warning(f"Storage HTTP PUT falló: {e}")
        return 0


def _http_post_json(url: str, headers: dict, payload: dict) -> int:
    """POST JSON; returns status code."""
    import json  # noqa: PLC0415
    body = json.dumps(payload).encode()
    h = {**headers, "Content-Type": "application/json"}
    try:
        import httpx  # noqa: PLC0415
        r = httpx.post(url, headers=h, content=body, timeout=15)
        return r.status_code
    except ImportError:
        pass
    try:
        import urllib.request  # noqa: PLC0415
        req = urllib.request.Request(url, data=body, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.getcode()
    except Exception:
        return 0


@property
def _enabled() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


_bucket_ensured = False


def _ensure_bucket() -> None:
    global _bucket_ensured
    if _bucket_ensured:
        return
    base = settings.supabase_url.rstrip("/")
    st = _http_post_json(
        f"{base}/storage/v1/bucket",
        _headers(),
        {"id": _BUCKET, "name": _BUCKET, "public": True},
    )
    # 200/201 = creado, 409 = ya existe — ambos son OK
    if st not in (200, 201, 409):
        logger.warning(f"Storage: no se pudo crear bucket ({st})")
    _bucket_ensured = True


def upload(file_path: Path, object_name: str, content_type: str = "audio/mpeg") -> str | None:
    """Sube el archivo a Supabase Storage. Devuelve URL pública o None."""
    if not (settings.supabase_url and settings.supabase_service_key):
        return None
    try:
        _ensure_bucket()
        base = settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/{_BUCKET}/{object_name}"
        with open(file_path, "rb") as f:
            data = f.read()
        h = {**_headers(), "Content-Type": content_type}
        st = _http_put(url, h, data)
        if st in (200, 201, 200):
            pub = f"{base}/storage/v1/object/public/{_BUCKET}/{object_name}"
            logger.info(f"Storage upload OK → {object_name}")
            return pub
        logger.warning(f"Storage upload {object_name}: HTTP {st}")
    except Exception as e:
        logger.warning(f"Storage upload error: {e}")
    return None


def delete(object_name: str) -> None:
    """Elimina el objeto de Supabase Storage (best-effort)."""
    if not (settings.supabase_url and settings.supabase_service_key):
        return
    try:
        import json  # noqa: PLC0415
        base = settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/{_BUCKET}"
        body = json.dumps({"prefixes": [object_name]}).encode()
        h = {**_headers(), "Content-Type": "application/json"}
        try:
            import httpx  # noqa: PLC0415
            httpx.delete(url, headers=h, content=body, timeout=10)
        except ImportError:
            import urllib.request  # noqa: PLC0415
            req = urllib.request.Request(url, data=body, headers=h, method="DELETE")
            urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Storage delete {object_name}: {e}")
