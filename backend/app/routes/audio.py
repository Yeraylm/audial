"""Endpoints de ingesta de audio y consulta de jobs."""
from __future__ import annotations

import shutil
from pathlib import Path

import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse as FastFileResponse, RedirectResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.etl.pipeline import process_single_audio
from pydantic import BaseModel

from app.models import Audio, Job, JobStatus, Transcript, get_db
from app.models.database import User
from app.models.schemas import AudioOut, JobOut
from app.services.auth_service import get_current_user
from app.services import storage as cloud_storage

router = APIRouter(prefix="/api/audio", tags=["audio"])

ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


class RenameIn(BaseModel):
    filename: str


def _session_id(request: Request) -> str:
    return request.headers.get("X-Session-ID", "") or ""


def _job_status_str(job) -> str:
    """Convierte JobStatus (enum o str) a string limpio."""
    if job is None:
        return "unknown"
    s = job.status
    if isinstance(s, JobStatus):
        return s.value
    # SQLite a veces devuelve el string directamente
    return str(s).split(".")[-1].lower()


@router.post("/upload", response_model=JobOut)
async def upload_audio(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    language: str | None = Form(None),
    ui_language: str | None = Form("es"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Extension '{ext}' no soportada. Usa: {ALLOWED_EXT}")

    session_id  = _session_id(request)
    output_lang = (ui_language or "es").lower()[:2]

    # Audios de invitado expiran en 24 h; los de usuarios registrados son permanentes
    expires = None if current_user else dt.datetime.utcnow() + dt.timedelta(hours=24)

    audio = Audio(
        filename=file.filename or "audio",
        filepath="", mime_type=file.content_type or "audio/mpeg",
        session_id=session_id, ui_language=output_lang,
        user_id=current_user.id if current_user else None,
        expires_at=expires,
    )
    db.add(audio); db.commit(); db.refresh(audio)

    dest = settings.audio_dir / f"{audio.id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    audio.filepath = str(dest)
    audio.size_bytes = dest.stat().st_size

    # Subir a Supabase Storage para persistencia tras reinicios de HF Spaces
    storage_url = cloud_storage.upload(dest, f"{audio.id}{ext}", audio.mime_type)
    if storage_url:
        audio.storage_url = storage_url
    db.commit()

    job = Job(audio_id=audio.id, status=JobStatus.PENDING, stage="queued", message="En cola")
    db.add(job); db.commit(); db.refresh(job)

    whisper_lang = None if not language or language == "auto" else language
    background.add_task(process_single_audio, audio.id, True, whisper_lang, output_lang)
    return job


@router.get("/", response_model=list[dict])
def list_audios(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    session_id = _session_id(request)
    result = []
    try:
        try:
            # filter() DEBE ir antes de limit() en SQLAlchemy
            q = db.query(Audio).order_by(Audio.uploaded_at.desc())
            if current_user:
                q = q.filter(Audio.user_id == current_user.id)
            elif session_id:
                q = q.filter(Audio.session_id == session_id)
            audios = q.limit(500).all()
        except Exception as _fe:
            logger.warning(f"Filtro de usuario falló ({_fe}), devolviendo todos")
            audios = db.query(Audio).order_by(Audio.uploaded_at.desc()).limit(500).all()

        for a in audios:
            try:
                latest_job = (
                    db.query(Job).filter(Job.audio_id == a.id)
                    .order_by(Job.id.desc()).first()
                )
                dur = float(a.duration_sec or 0.0)
                # Backfill duration from transcript segments if not stored
                if dur == 0:
                    try:
                        tr = db.query(Transcript).filter(Transcript.audio_id == a.id).first()
                        if tr and isinstance(tr.segments_json, dict):
                            segs = tr.segments_json.get("segments", [])
                            if segs:
                                dur = max(
                                    (float(s.get("end", 0)) for s in segs if isinstance(s, dict)),
                                    default=0.0,
                                )
                                if dur > 0:
                                    a.duration_sec = dur
                                    db.commit()
                    except Exception:
                        pass
                result.append({
                    "id":          str(a.id),
                    "filename":    str(a.filename or ""),
                    "size_bytes":  int(a.size_bytes or 0),
                    "duration_sec": dur,
                    "mime_type":   str(a.mime_type or "audio/mpeg"),
                    "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
                    "expires_at":  a.expires_at.isoformat() if a.expires_at else None,
                    "is_guest":    a.user_id is None,
                    "job_status":  _job_status_str(latest_job),
                    "job_stage":   str(latest_job.stage   if latest_job else ""),
                    "job_message": str(latest_job.message if latest_job else ""),
                })
            except Exception as e:
                logger.warning(f"Skip audio {getattr(a,'id','?')}: {e}")
    except Exception as e:
        logger.exception("Error crítico en list_audios")
        # Devolver lista vacía en lugar de 500 para no romper el frontend
        return []
    return result


@router.get("/{audio_id}", response_model=AudioOut)
def get_audio(audio_id: str, db: Session = Depends(get_db)):
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    return a


@router.get("/{audio_id}/jobs", response_model=list[JobOut])
def audio_jobs(audio_id: str, db: Session = Depends(get_db)):
    return db.query(Job).filter(Job.audio_id == audio_id).order_by(Job.id.desc()).all()


@router.get("/job/{job_id}", response_model=JobOut)
def job_status(job_id: str, db: Session = Depends(get_db)):
    j = db.query(Job).filter(Job.id == job_id).first()
    if not j:
        raise HTTPException(404, "Job no encontrado")
    return j


@router.get("/{audio_id}/file")
def stream_audio(audio_id: str, db: Session = Depends(get_db)):
    """Sirve el archivo de audio. Intenta disco local primero, luego Supabase Storage."""
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    p = Path(a.filepath) if a.filepath else None
    if p and p.exists():
        media_type = a.mime_type or "audio/mpeg"
        return FastFileResponse(str(p), media_type=media_type, headers={"Accept-Ranges": "bytes"})
    # Fallback: redirigir a Supabase Storage si el archivo local fue borrado
    if getattr(a, "storage_url", None):
        return RedirectResponse(url=a.storage_url, status_code=302)
    raise HTTPException(404, "Archivo de audio no disponible")


@router.delete("/{audio_id}")
def delete_audio(audio_id: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    try:
        Path(a.filepath).unlink(missing_ok=True)
    except Exception:
        pass
    # Eliminar también de Supabase Storage
    if getattr(a, "storage_url", None):
        ext = Path(a.filepath).suffix if a.filepath else ""
        cloud_storage.delete(f"{audio_id}{ext}")
    db.delete(a); db.commit()
    return {"deleted": audio_id}


@router.post("/{audio_id}/reupload")
async def reupload_audio(
    audio_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Re-sube el fichero de audio sin borrar el análisis existente."""
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Extensión '{ext}' no soportada")
    dest = settings.audio_dir / f"{audio_id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    a.filepath   = str(dest)
    a.size_bytes = dest.stat().st_size
    storage_url  = cloud_storage.upload(dest, f"{audio_id}{ext}", a.mime_type or "audio/mpeg")
    if storage_url:
        a.storage_url = storage_url
    db.commit()
    return {"id": audio_id, "storage_url": storage_url}


@router.patch("/{audio_id}/rename")
def rename_audio(audio_id: str, body: RenameIn, db: Session = Depends(get_db)):
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    name = body.filename.strip()
    if not name:
        raise HTTPException(400, "Nombre requerido")
    a.filename = name
    db.commit()
    return {"id": audio_id, "filename": name}
