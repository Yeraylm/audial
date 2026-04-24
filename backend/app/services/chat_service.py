"""Asistente conversacional RAG sobre las transcripciones indexadas."""
from __future__ import annotations

from typing import Any

from app.services.embeddings import embedding_service
from app.services.llm_service import llm
from app.services.prompts import CHAT_RAG


def answer_question(question: str, audio_id: str | None = None, top_k: int = 5) -> dict[str, Any]:
    hits = embedding_service.search(question, top_k=top_k, audio_id=audio_id)
    if not hits:
        return {"answer": "No hay contenido indexado para responder.", "sources": []}

    context_parts = []
    for h in hits:
        context_parts.append(f"(seg {h.segment_idx} | audio {h.audio_id[:8]}) {h.text}")
    context = "\n".join(context_parts)

    answer = llm.complete(CHAT_RAG.format(question=question, context=context), temperature=0.2)
    return {
        "answer": answer or "No pude generar una respuesta.",
        "sources": [
            {"audio_id": h.audio_id, "segment_idx": h.segment_idx, "score": round(h.score, 3), "text": h.text}
            for h in hits
        ],
    }
