"""Limpieza periodica de audios de invitado expirados.

Los audios subidos por usuarios no registrados tienen expires_at = now + 24h.
Esta tarea se ejecuta cada hora y elimina:
  - El registro de BD (cascade elimina transcript, analysis, jobs)
  - El archivo de audio del disco
"""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from loguru import logger

from app.models.database import Audio, SessionLocal


async def cleanup_guest_audios() -> None:
    """Elimina audios de invitado cuya fecha de expiración ya pasó."""
    db = SessionLocal()
    try:
        now = dt.datetime.utcnow()
        expired = (
            db.query(Audio)
            .filter(Audio.user_id == None, Audio.expires_at <= now)  # noqa: E711
            .all()
        )
        if not expired:
            return
        logger.info(f"Limpieza: eliminando {len(expired)} audio(s) de invitado expirados")
        for audio in expired:
            try:
                Path(audio.filepath).unlink(missing_ok=True)
            except Exception:
                pass
            db.delete(audio)
        db.commit()
        logger.info("Limpieza completada")
    except Exception as e:
        logger.warning(f"Error en limpieza de audios: {e}")
        db.rollback()
    finally:
        db.close()


async def run_periodic_cleanup(interval_seconds: int = 3600) -> None:
    """Bucle infinito que ejecuta la limpieza cada `interval_seconds`."""
    while True:
        await asyncio.sleep(interval_seconds)
        await cleanup_guest_audios()
