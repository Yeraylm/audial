"""Endpoints agregados para el dashboard analitico."""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Analysis, Audio, get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _safe_items(val: Any) -> list:
    """Extrae una lista de items de forma segura sea val list o dict."""
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        items = val.get("items", [])
        return items if isinstance(items, list) else []
    return []


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    try:
        total_audios    = db.query(Audio).count()
        total_analyses  = db.query(Analysis).count()
        total_duration  = 0.0
        sentiments: Counter = Counter()
        tasks = decisions = conflicts = 0

        for a in db.query(Analysis).all():
            try:
                total_duration += _safe_float((a.metrics or {}).get("total_duration_sec"))
                lbl = (a.sentiment or {}).get("global", {}).get("label") or "neutro"
                sentiments[str(lbl)] += 1
                tasks     += len(_safe_items(a.tasks))
                decisions += len(_safe_items(a.decisions))
                conflicts += len(_safe_items(a.conflicts))
            except Exception as e:
                logger.warning(f"Dashboard: error procesando analysis {getattr(a,'id','?')}: {e}")

        return {
            "total_audios":          total_audios,
            "total_analyses":        total_analyses,
            "total_duration_hours":  round(total_duration / 3600, 2),
            "sentiment_distribution": dict(sentiments),
            "totals": {"tasks": tasks, "decisions": decisions, "conflicts": conflicts},
        }
    except Exception as e:
        logger.exception("Error en dashboard overview")
        raise HTTPException(500, f"Dashboard error: {e}")


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
        logger.warning(f"Related audios error: {e}")
        return []
