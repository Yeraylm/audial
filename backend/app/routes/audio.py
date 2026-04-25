"""Endpoints de ingesta de audio y consulta de jobs."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse as FastFileResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.etl.pipeline import process_single_audio
from app.models import Audio, Job, JobStatus, get_db
from app.models.database import User
from app.models.schemas import AudioOut, JobOut
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/audio", tags=["audio"])

ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


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

    audio = Audio(
        filename=file.filename or "audio",
        filepath="", mime_type=file.content_type or "audio/mpeg",
        session_id=session_id, ui_language=output_lang,
        user_id=current_user.id if current_user else None,
    )
    db.add(audio); db.commit(); db.refresh(audio)

    dest = settings.audio_dir / f"{audio.id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    audio.filepath = str(dest)
    audio.size_bytes = dest.stat().st_size
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
            q = db.query(Audio).order_by(Audio.uploaded_at.desc()).limit(500)
            if current_user:
                # Usuario autenticado: ver solo SUS audios
                q = q.filter(Audio.user_id == current_user.id)
            elif session_id:
                # Invitado: filtrar por session_id (solo audios sin user_id)
                q = q.filter(Audio.user_id == None, Audio.session_id == session_id)  # noqa: E711
            audios = q.all()
        except Exception:
            logger.warning("Filtro de usuario falló, devolviendo todos")
            audios = db.query(Audio).order_by(Audio.uploaded_at.desc()).limit(500).all()

        for a in audios:
            try:
                latest_job = (
                    db.query(Job).filter(Job.audio_id == a.id)
                    .order_by(Job.id.desc()).first()
                )
                result.append({
                    "id":          str(a.id),
                    "filename":    str(a.filename or ""),
                    "size_bytes":  int(a.size_bytes or 0),
                    "duration_sec":float(a.duration_sec or 0.0),
                    "mime_type":   str(a.mime_type or "audio/mpeg"),
                    "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
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
    """Sirve el archivo de audio original para el reproductor del frontend."""
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    p = Path(a.filepath)
    if not p.exists():
        raise HTTPException(404, "Archivo de audio no encontrado en disco")
    media_type = a.mime_type or "audio/mpeg"
    return FastFileResponse(str(p), media_type=media_type, headers={"Accept-Ranges": "bytes"})


@router.delete("/{audio_id}")
def delete_audio(audio_id: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    try:
        Path(a.filepath).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete(a); db.commit()
    return {"deleted": audio_id}
