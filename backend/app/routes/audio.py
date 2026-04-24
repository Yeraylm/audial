"""Endpoints de ingesta de audio y consulta de jobs."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.etl.pipeline import process_single_audio
from app.models import Audio, Job, JobStatus, get_db
from app.models.schemas import AudioOut, JobOut

router = APIRouter(prefix="/api/audio", tags=["audio"])

ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def _session_id(request: Request) -> str:
    return request.headers.get("X-Session-ID", "")


@router.post("/upload", response_model=JobOut)
async def upload_audio(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    language: str | None = Form(None),      # idioma del AUDIO para Whisper (es/en/None=auto)
    ui_language: str | None = Form("es"),   # idioma de la UI para el output del LLM
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Extension '{ext}' no soportada. Usa: {ALLOWED_EXT}")

    session_id = _session_id(request)
    output_lang = (ui_language or "es").lower()[:2]  # 'es' | 'en'

    audio = Audio(
        filename=file.filename or "audio",
        filepath="",
        mime_type=file.content_type or "audio/mpeg",
        session_id=session_id,
        ui_language=output_lang,
    )
    db.add(audio)
    db.commit()
    db.refresh(audio)

    dest = settings.audio_dir / f"{audio.id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    audio.filepath = str(dest)
    audio.size_bytes = dest.stat().st_size
    db.commit()

    job = Job(audio_id=audio.id, status=JobStatus.PENDING, stage="queued", message="En cola")
    db.add(job)
    db.commit()
    db.refresh(job)

    whisper_lang = None if not language or language == "auto" else language
    background.add_task(process_single_audio, audio.id, True, whisper_lang, output_lang)
    return job


@router.get("/", response_model=list[dict])
def list_audios(request: Request, db: Session = Depends(get_db)):
    session_id = _session_id(request)
    q = db.query(Audio).order_by(Audio.uploaded_at.desc()).limit(500)
    if session_id:
        q = q.filter(Audio.session_id == session_id)
    audios = q.all()

    result = []
    for a in audios:
        latest_job = (
            db.query(Job).filter(Job.audio_id == a.id).order_by(Job.id.desc()).first()
        )
        result.append({
            "id": a.id,
            "filename": a.filename,
            "size_bytes": a.size_bytes,
            "duration_sec": a.duration_sec,
            "mime_type": a.mime_type,
            "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
            "job_status":  latest_job.status.value if latest_job else "unknown",
            "job_stage":   latest_job.stage         if latest_job else "",
            "job_message": latest_job.message       if latest_job else "",
        })
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


@router.delete("/{audio_id}")
def delete_audio(audio_id: str, request: Request, db: Session = Depends(get_db)):
    a = db.query(Audio).filter(Audio.id == audio_id).first()
    if not a:
        raise HTTPException(404, "Audio no encontrado")
    try:
        Path(a.filepath).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete(a)
    db.commit()
    return {"deleted": audio_id}
