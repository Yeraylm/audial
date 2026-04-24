"""Endpoints agregados para el dashboard analitico."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import Analysis, Audio, get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    total_audios = db.query(Audio).count()
    total_analyses = db.query(Analysis).count()
    total_duration = 0.0
    sentiments: Counter = Counter()
    tasks = 0
    decisions = 0
    conflicts = 0
    for a in db.query(Analysis).all():
        total_duration += (a.metrics or {}).get("total_duration_sec", 0.0) or 0.0
        lbl = (a.sentiment or {}).get("global", {}).get("label") or "neutro"
        sentiments[lbl] += 1
        tasks += len((a.tasks or {}).get("items", []))
        decisions += len((a.decisions or {}).get("items", []))
        conflicts += len((a.conflicts or {}).get("items", []))
    return {
        "total_audios": total_audios,
        "total_analyses": total_analyses,
        "total_duration_hours": round(total_duration / 3600, 2),
        "sentiment_distribution": dict(sentiments),
        "totals": {"tasks": tasks, "decisions": decisions, "conflicts": conflicts},
    }


@router.get("/related/{audio_id}")
def related_audios(audio_id: str, db: Session = Depends(get_db), top_k: int = 5):
    """Relaciona audios usando su resumen medio + embeddings."""
    from app.services.embeddings import embedding_service

    a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if not a or not a.summary_medium:
        return []
    hits = embedding_service.search(a.summary_medium, top_k=top_k * 4)
    # filtrar auto-referencia y deduplicar por audio
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
