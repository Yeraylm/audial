"""Endpoints de consulta de transcripciones, analisis y traduccion."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Analysis, Audio, Transcript, get_db
from app.models.schemas import AnalysisOut, TranscriptOut, TranscriptSegment
from app.services.exporter import export_json, export_pdf
from app.services.llm_service import llm

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Cache en memoria: {audio_id}_{lang} -> AnalysisOut dict
_translation_cache: dict[str, dict[str, Any]] = {}


def _analysis_to_out(a: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=a.id, audio_id=a.audio_id,
        summary_short=a.summary_short, summary_medium=a.summary_medium, summary_long=a.summary_long,
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


def _translate_text(text: str, target: str) -> str:
    """Traduce un texto usando el LLM configurado."""
    if not text or not text.strip():
        return text
    lang_name = "English" if target.startswith("en") else "Spanish"
    prompt = (
        f"Translate the following text to {lang_name}. "
        "Return ONLY the translated text, no explanations, no quotes.\n\n"
        f"{text}"
    )
    result = llm.complete(prompt, temperature=0.1, max_tokens=1024)
    return result.strip() if result else text


def _translate_list_of_dicts(items: list[dict], target: str, keys: list[str]) -> list[dict]:
    """Traduce campos de texto en una lista de dicts."""
    translated = []
    for item in items:
        new = dict(item)
        for k in keys:
            if k in new and isinstance(new[k], str) and new[k]:
                new[k] = _translate_text(new[k], target)
        translated.append(new)
    return translated


def _translate_analysis(analysis_dict: dict[str, Any], target: str) -> dict[str, Any]:
    """Traduce todos los campos de texto de un analysis al idioma target."""
    logger.info(f"Traduciendo análisis al idioma: {target}")
    d = dict(analysis_dict)
    d["summary_short"]  = _translate_text(d.get("summary_short", ""), target)
    d["summary_medium"] = _translate_text(d.get("summary_medium", ""), target)
    d["summary_long"]   = _translate_text(d.get("summary_long", ""), target)
    d["tasks"]      = _translate_list_of_dicts(d.get("tasks", []),      target, ["task", "owner", "deadline"])
    d["decisions"]  = _translate_list_of_dicts(d.get("decisions", []),  target, ["decision", "rationale", "made_by"])
    d["questions"]  = _translate_list_of_dicts(d.get("questions", []),  target, ["question", "answer_summary"])
    d["topics"]     = _translate_list_of_dicts(d.get("topics", []),     target, ["topic", "summary"])
    d["timeline"]   = _translate_list_of_dicts(d.get("timeline", []),   target, ["event", "speaker"])
    d["intents"]    = _translate_list_of_dicts(d.get("intents", []),    target, ["intent", "evidence"])
    d["conflicts"]  = _translate_list_of_dicts(d.get("conflicts", []),  target, ["topic", "evidence"])
    # entities: translate values within each category
    entities = d.get("entities", {})
    if isinstance(entities, dict):
        new_ent = {}
        for cat, items in entities.items():
            cat_translated = _translate_text(cat, target)
            if isinstance(items, list):
                new_items = []
                for item in items:
                    if isinstance(item, str):
                        new_items.append(_translate_text(item, target))
                    elif isinstance(item, dict):
                        ni = dict(item)
                        for k in ("name", "role", "description"):
                            if k in ni and isinstance(ni[k], str):
                                ni[k] = _translate_text(ni[k], target)
                        new_items.append(ni)
                    else:
                        new_items.append(item)
                new_ent[cat_translated] = new_items
            else:
                new_ent[cat_translated] = items
        d["entities"] = new_ent
    return d


@router.get("/{audio_id}/transcript", response_model=TranscriptOut)
def get_transcript(audio_id: str, db: Session = Depends(get_db)):
    t = db.query(Transcript).filter(Transcript.audio_id == audio_id).first()
    if not t:
        raise HTTPException(404, "Transcripcion no disponible")
    segs_raw = (t.segments_json or {}).get("segments", [])
    segments = [TranscriptSegment(**s) for s in segs_raw]
    return TranscriptOut(
        id=t.id, audio_id=t.audio_id, language=t.language,
        full_text=t.full_text, cleaned_text=t.cleaned_text, segments=segments,
    )


@router.get("/{audio_id}", response_model=AnalysisOut)
def get_analysis(
    audio_id: str,
    lang: str | None = Query(None, description="Idioma destino (es/en). Si difiere del original, se traduce."),
    db: Session = Depends(get_db),
):
    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a:
        raise HTTPException(404, "Analisis no disponible")

    base = _analysis_to_out(a)

    # Si no se pide traducción o es el mismo idioma, devolver directo
    if not lang or not lang.strip():
        return base

    target = lang.strip()[:2].lower()
    # Detectar idioma original del audio
    audio = db.query(Audio).filter(Audio.id == audio_id).first()
    original_lang = (getattr(audio, "ui_language", None) or "es")[:2].lower()

    if target == original_lang:
        return base

    # Buscar en caché
    cache_key = f"{audio_id}_{target}"
    if cache_key in _translation_cache:
        logger.info(f"Traducción desde caché: {cache_key}")
        cached = _translation_cache[cache_key]
        return AnalysisOut(**cached)

    # Traducir
    try:
        base_dict = base.model_dump()
        translated_dict = _translate_analysis(base_dict, target)
        _translation_cache[cache_key] = translated_dict
        return AnalysisOut(**translated_dict)
    except Exception as e:
        logger.warning(f"Traducción falló ({e}), devolviendo original")
        return base


@router.get("/{audio_id}/export.json")
def export_analysis_json(audio_id: str, db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a:
        raise HTTPException(404, "Analisis no disponible")
    payload = {
        "summary_short": a.summary_short, "summary_medium": a.summary_medium,
        "summary_long": a.summary_long, "entities": a.entities or {},
        "tasks": (a.tasks or {}).get("items", []),
        "decisions": (a.decisions or {}).get("items", []),
        "questions": (a.questions or {}).get("items", []),
        "topics": (a.topics or {}).get("items", []),
        "timeline": (a.timeline or {}).get("items", []),
        "intents": (a.intents or {}).get("items", []),
        "sentiment": a.sentiment or {}, "conflicts": (a.conflicts or {}).get("items", []),
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
        "summary_short": a.summary_short, "summary_medium": a.summary_medium,
        "summary_long": a.summary_long, "entities": a.entities or {},
        "tasks": (a.tasks or {}).get("items", []),
        "decisions": (a.decisions or {}).get("items", []),
        "questions": (a.questions or {}).get("items", []),
        "sentiment": a.sentiment or {}, "conflicts": (a.conflicts or {}).get("items", []),
        "metrics": a.metrics or {},
    }
    path = export_pdf(audio_id, payload)
    return FileResponse(path, filename=path.name, media_type="application/pdf")
