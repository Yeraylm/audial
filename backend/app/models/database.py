"""Definicion del modelo relacional y sesion SQLAlchemy.

El esquema esta pensado para soportar indistintamente SQLite (desarrollo) o
PostgreSQL (produccion). Se modelan cinco entidades principales:

- Audio: archivo fuente ingerido por el pipeline.
- Job: estado del procesamiento asincrono.
- Transcript: texto resultante de Whisper con timestamps y hablantes.
- Analysis: resultado estructurado del LLM (resumen, entidades, sentimiento...).
- EmbeddingIndex: pointer al vector almacenado en Chroma/FAISS.
"""
from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Audio(Base):
    __tablename__ = "audios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(512))
    filepath: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    mime_type: Mapped[str] = mapped_column(String(128), default="audio/mpeg")
    uploaded_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    # Multi-user isolation (session UUID from browser localStorage)
    session_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    # UI language → controls LLM output language (es/en)
    ui_language: Mapped[str] = mapped_column(String(8), default="es")

    jobs = relationship("Job", back_populates="audio", cascade="all, delete")
    transcript = relationship("Transcript", back_populates="audio", uselist=False, cascade="all, delete")
    analysis = relationship("Analysis", back_populates="audio", uselist=False, cascade="all, delete")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id: Mapped[str] = mapped_column(ForeignKey("audios.id"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    audio = relationship("Audio", back_populates="jobs")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id: Mapped[str] = mapped_column(ForeignKey("audios.id"), unique=True)
    language: Mapped[str] = mapped_column(String(8), default="es")
    full_text: Mapped[str] = mapped_column(Text)
    segments_json: Mapped[Any] = mapped_column(JSON, default=dict)
    cleaned_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audio = relationship("Audio", back_populates="transcript")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id: Mapped[str] = mapped_column(ForeignKey("audios.id"), unique=True)
    summary_short: Mapped[str] = mapped_column(Text, default="")
    summary_medium: Mapped[str] = mapped_column(Text, default="")
    summary_long: Mapped[str] = mapped_column(Text, default="")
    # Any porque el LLM puede devolver list o dict segun el prompt
    entities: Mapped[Any] = mapped_column(JSON, default=dict)
    tasks: Mapped[Any] = mapped_column(JSON, default=dict)
    decisions: Mapped[Any] = mapped_column(JSON, default=dict)
    questions: Mapped[Any] = mapped_column(JSON, default=dict)
    topics: Mapped[Any] = mapped_column(JSON, default=dict)
    timeline: Mapped[Any] = mapped_column(JSON, default=dict)
    intents: Mapped[Any] = mapped_column(JSON, default=dict)
    sentiment: Mapped[Any] = mapped_column(JSON, default=dict)
    conflicts: Mapped[Any] = mapped_column(JSON, default=dict)
    metrics: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audio = relationship("Audio", back_populates="analysis")


class EmbeddingIndex(Base):
    __tablename__ = "embeddings_index"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id: Mapped[str] = mapped_column(ForeignKey("audios.id"))
    segment_idx: Mapped[int] = mapped_column(Integer, default=0)
    backend: Mapped[str] = mapped_column(String(16), default="chroma")
    vector_ref: Mapped[str] = mapped_column(String(128))
    text_excerpt: Mapped[str] = mapped_column(Text)


# --- Engine / session helpers ---
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
