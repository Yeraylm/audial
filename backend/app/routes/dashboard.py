"""Dashboard overview y audios relacionados."""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Analysis, Audio, get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_EMPTY = {
    "total_audios": 0, "total_analyses": 0, "total_duration_hours": 0.0,
    "sentiment_distribution": {}, "totals": {"tasks": 0, "decisions": 0, "conflicts": 0},
}


def _safe_items(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        items = val.get("items", [])
        return items if isinstance(items, list) else []
    return []


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    # Total audios — consulta básica, no puede fallar si la tabla existe
    try:
        total_audios = db.query(Audio).count()
    except Exception as e:
        logger.warning(f"Dashboard: tabla audios no disponible: {e}")
        return _EMPTY

    try:
        total_analyses = db.query(Analysis).count()
    except Exception as e:
        logger.warning(f"Dashboard: tabla analyses no disponible: {e}")
        return {**_EMPTY, "total_audios": total_audios}

    total_duration = 0.0
    sentiments: Counter = Counter()
    tasks = decisions = conflicts = 0

    try:
        for a in db.query(Analysis).all():
            try:
                total_duration += float((a.metrics or {}).get("total_duration_sec") or 0)
                lbl = str((a.sentiment or {}).get("global", {}).get("label") or "neutro")
                sentiments[lbl] += 1
                tasks     += len(_safe_items(a.tasks))
                decisions += len(_safe_items(a.decisions))
                conflicts += len(_safe_items(a.conflicts))
            except Exception:
                pass  # Saltar análisis problemático
    except Exception as e:
        logger.warning(f"Dashboard: error iterando analyses: {e}")

    return {
        "total_audios": total_audios,
        "total_analyses": total_analyses,
        "total_duration_hours": round(total_duration / 3600, 2),
        "sentiment_distribution": dict(sentiments),
        "totals": {"tasks": tasks, "decisions": decisions, "conflicts": conflicts},
    }


@router.get("/related/{audio_id}")
def related_audios(audio_id: str, db: Session = Depends(get_db), top_k: int = 5):
    try:
        from app.services.embeddings import embedding_service
        a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
        if not a or not a.summary_medium:
            return []
        hits = embedding_service.search(a.summary_medium, top_k=top_k * 4)
        seen: set[str] = set()
        out = []
        for h in hits:
            if h.audio_id == audio_id or h.audio_id in seen:
                continue
            seen.add(h.audio_id)
            out.append({"audio_id": h.audio_id, "score": round(h.score, 3), "excerpt": h.text[:200]})
            if len(out) >= top_k:
                break
        return out
    except Exception as e:
        logger.warning(f"Related error: {e}")
        return []
