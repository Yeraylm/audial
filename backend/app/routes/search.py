"""Endpoints de busqueda semantica y chat RAG."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.models.schemas import ChatRequest, ChatResponse, SearchHit, SearchRequest
from app.services.chat_service import answer_question
from app.services.embeddings import embedding_service

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=list[SearchHit])
def semantic_search(req: SearchRequest):
    try:
        hits = embedding_service.search(req.query, top_k=req.top_k, audio_id=req.audio_id)
        return [
            SearchHit(audio_id=h.audio_id, segment_idx=h.segment_idx, text=h.text, score=h.score)
            for h in hits
        ]
    except Exception as e:
        logger.warning(f"Busqueda semantica fallo: {e}")
        return []


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        data = answer_question(req.message, audio_id=req.audio_id, top_k=req.top_k)
        return ChatResponse(answer=data["answer"], sources=data["sources"])
    except Exception as e:
        logger.error(f"Chat RAG fallo: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"El asistente no esta disponible: {str(e)}. "
                   "Asegurate de que Ollama esta ejecutandose (ollama serve) "
                   "y hay al menos un audio procesado con embeddings.",
        )
