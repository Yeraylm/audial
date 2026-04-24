"""Endpoints de consulta de transcripciones y analisis."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models import Analysis, Audio, Transcript, get_db
from app.models.schemas import AnalysisOut, TranscriptOut, TranscriptSegment
from app.services.exporter import export_json, export_pdf

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{audio_id}/transcript", response_model=TranscriptOut)
def get_transcript(audio_id: str, db: Session = Depends(get_db)):
    t = db.query(Transcript).filter(Transcript.audio_id == audio_id).first()
    if not t:
        raise HTTPException(404, "Transcripcion aun no disponible")
    segs_raw = (t.segments_json or {}).get("segments", [])
    segments = [TranscriptSegment(**s) for s in segs_raw]
    return TranscriptOut(
        id=t.id,
        audio_id=t.audio_id,
        language=t.language,
        full_text=t.full_text,
        cleaned_text=t.cleaned_text,
        segments=segments,
    )


@router.get("/{audio_id}", response_model=AnalysisOut)
def get_analysis(audio_id: str, db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a:
        raise HTTPException(404, "Analisis aun no disponible")
    return AnalysisOut(
        id=a.id,
        audio_id=a.audio_id,
        summary_short=a.summary_short,
        summary_medium=a.summary_medium,
        summary_long=a.summary_long,
        entities=a.entities or {},
        tasks=(a.tasks or {}).get("items", []),
        decisions=(a.decisions or {}).get("items", []),
        questions=(a.questions or {}).get("items", []),
        topics=(a.topics or {}).get("items", []),
        timeline=(a.timeline or {}).get("items", []),
        intents=(a.intents or {}).get("items", []),
        sentiment=a.sentiment or {},
        conflicts=(a.conflicts or {}).get("items", []),
        metrics=a.metrics or {},
    )


@router.get("/{audio_id}/export.json")
def export_analysis_json(audio_id: str, db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a:
        raise HTTPException(404, "Analisis no disponible")
    payload = {
        "summary_short": a.summary_short,
        "summary_medium": a.summary_medium,
        "summary_long": a.summary_long,
        "entities": a.entities or {},
        "tasks": (a.tasks or {}).get("items", []),
        "decisions": (a.decisions or {}).get("items", []),
        "questions": (a.questions or {}).get("items", []),
        "topics": (a.topics or {}).get("items", []),
        "timeline": (a.timeline or {}).get("items", []),
        "intents": (a.intents or {}).get("items", []),
        "sentiment": a.sentiment or {},
        "conflicts": (a.conflicts or {}).get("items", []),
        "metrics": a.metrics or {},
    }
    path = export_json(audio_id, payload)
    return FileResponse(path, filename=path.name, media_type="application/json")


@router.get("/{audio_id}/export.pdf")
def export_analysis_pdf(audio_id: str, db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a:
        raise HTTPException(404, "Analisis no disponible")
    payload = {
        "summary_short": a.summary_short,
        "summary_medium": a.summary_medium,
        "summary_long": a.summary_long,
        "entities": a.entities or {},
        "tasks": (a.tasks or {}).get("items", []),
        "decisions": (a.decisions or {}).get("items", []),
        "questions": (a.questions or {}).get("items", []),
        "sentiment": a.sentiment or {},
        "conflicts": (a.conflicts or {}).get("items", []),
        "metrics": a.metrics or {},
    }
    path = export_pdf(audio_id, payload)
    return FileResponse(path, filename=path.name, media_type="application/pdf")
