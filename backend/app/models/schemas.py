"""Esquemas Pydantic expuestos por la API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AudioOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    duration_sec: float
    mime_type: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    audio_id: str
    status: str
    stage: str
    progress: float
    message: str

    class Config:
        from_attributes = True


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None


class TranscriptOut(BaseModel):
    id: str
    audio_id: str
    language: str
    full_text: str
    cleaned_text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class AnalysisOut(BaseModel):
    id: str
    audio_id: str
    summary_short: str
    summary_medium: str
    summary_long: str
    entities: dict[str, Any]
    tasks: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    intents: list[dict[str, Any]]
    sentiment: dict[str, Any]
    conflicts: list[dict[str, Any]]
    metrics: dict[str, Any]


class ChatRequest(BaseModel):
    audio_id: str | None = None
    message: str
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    audio_id: str | None = None


class SearchHit(BaseModel):
    audio_id: str
    segment_idx: int
    text: str
    score: float
