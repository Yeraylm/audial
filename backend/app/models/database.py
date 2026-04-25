"""Modelo relacional y sesión SQLAlchemy.

init_db() garantiza que las columnas nuevas (session_id, ui_language)
existen incluso si la BD fue creada por una versión anterior del código.
"""
from __future__ import annotations

import datetime as dt
import enum
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import (
    JSON, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, create_engine, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


class User(Base):
    __tablename__ = "users"

    id:                  Mapped[str]          = mapped_column(String(64), primary_key=True, default=_uuid)
    email:               Mapped[str]          = mapped_column(String(256), unique=True)
    display_name:        Mapped[str]          = mapped_column(String(128), default="")
    hashed_password:     Mapped[str]          = mapped_column(String(256))
    is_verified:         Mapped[int]          = mapped_column(Integer, default=0)   # 0=no, 1=sí
    verification_token:  Mapped[str|None]     = mapped_column(String(128), nullable=True)
    reset_token:         Mapped[str|None]     = mapped_column(String(128), nullable=True)
    reset_token_exp:     Mapped[dt.datetime|None] = mapped_column(DateTime, nullable=True)
    created_at:          Mapped[dt.datetime]  = mapped_column(DateTime, default=dt.datetime.utcnow)

    # Sin relacion ORM directa — filtramos Audio por user_id directamente en las queries


class Audio(Base):
    __tablename__ = "audios"

    id:          Mapped[str]          = mapped_column(String(64), primary_key=True, default=_uuid)
    filename:    Mapped[str]          = mapped_column(String(512))
    filepath:    Mapped[str]          = mapped_column(String(1024))
    size_bytes:  Mapped[int]          = mapped_column(Integer, default=0)
    duration_sec:Mapped[float]        = mapped_column(Float, default=0.0)
    mime_type:   Mapped[str]          = mapped_column(String(128), default="audio/mpeg")
    uploaded_at: Mapped[dt.datetime]  = mapped_column(DateTime, default=dt.datetime.utcnow)
    session_id:  Mapped[str]          = mapped_column(String(64), default="")
    ui_language: Mapped[str]          = mapped_column(String(8),  default="es")
    # Auth: si el usuario está logueado, se guarda aquí; si no, se usa session_id
    # Sin ForeignKey explícita para evitar conflictos de relación ORM — filtramos manualmente
    user_id:     Mapped[str|None]     = mapped_column(String(64), nullable=True)

    jobs       = relationship("Job",        back_populates="audio", cascade="all, delete")
    transcript = relationship("Transcript", back_populates="audio", uselist=False, cascade="all, delete")
    analysis   = relationship("Analysis",   back_populates="audio", uselist=False, cascade="all, delete")


class Job(Base):
    __tablename__ = "jobs"

    id:          Mapped[str]              = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id:    Mapped[str]              = mapped_column(ForeignKey("audios.id"))
    status:      Mapped[JobStatus]        = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    stage:       Mapped[str]              = mapped_column(String(64), default="queued")
    progress:    Mapped[float]            = mapped_column(Float, default=0.0)
    message:     Mapped[str]              = mapped_column(Text, default="")
    started_at:  Mapped[dt.datetime|None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime|None] = mapped_column(DateTime, nullable=True)

    audio = relationship("Audio", back_populates="jobs")


class Transcript(Base):
    __tablename__ = "transcripts"

    id:           Mapped[str]          = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id:     Mapped[str]          = mapped_column(ForeignKey("audios.id"), unique=True)
    language:     Mapped[str]          = mapped_column(String(8), default="es")
    full_text:    Mapped[str]          = mapped_column(Text)
    segments_json:Mapped[Any]          = mapped_column(JSON, default=dict)
    cleaned_text: Mapped[str]          = mapped_column(Text, default="")
    created_at:   Mapped[dt.datetime]  = mapped_column(DateTime, default=dt.datetime.utcnow)

    audio = relationship("Audio", back_populates="transcript")


class Analysis(Base):
    __tablename__ = "analyses"

    id:             Mapped[str]         = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id:       Mapped[str]         = mapped_column(ForeignKey("audios.id"), unique=True)
    summary_short:  Mapped[str]         = mapped_column(Text, default="")
    summary_medium: Mapped[str]         = mapped_column(Text, default="")
    summary_long:   Mapped[str]         = mapped_column(Text, default="")
    entities:       Mapped[Any]         = mapped_column(JSON, default=dict)
    tasks:          Mapped[Any]         = mapped_column(JSON, default=dict)
    decisions:      Mapped[Any]         = mapped_column(JSON, default=dict)
    questions:      Mapped[Any]         = mapped_column(JSON, default=dict)
    topics:         Mapped[Any]         = mapped_column(JSON, default=dict)
    timeline:       Mapped[Any]         = mapped_column(JSON, default=dict)
    intents:        Mapped[Any]         = mapped_column(JSON, default=dict)
    sentiment:      Mapped[Any]         = mapped_column(JSON, default=dict)
    conflicts:      Mapped[Any]         = mapped_column(JSON, default=dict)
    metrics:        Mapped[Any]         = mapped_column(JSON, default=dict)
    created_at:     Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audio = relationship("Audio", back_populates="analysis")


class EmbeddingIndex(Base):
    __tablename__ = "embeddings_index"

    id:          Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    audio_id:    Mapped[str] = mapped_column(ForeignKey("audios.id"))
    segment_idx: Mapped[int] = mapped_column(Integer, default=0)
    backend:     Mapped[str] = mapped_column(String(16), default="chroma")
    vector_ref:  Mapped[str] = mapped_column(String(128))
    text_excerpt:Mapped[str] = mapped_column(Text)


# ── Engine / session ──────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _add_column_if_missing(conn, table: str, col: str, col_def: str) -> None:
    """Añade una columna si no existe — compatible con SQLite y PostgreSQL."""
    try:
        if settings.database_url.startswith("sqlite"):
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = [r[1] for r in rows]
        else:
            rows = conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table}'"
            )).fetchall()
            existing = [r[0] for r in rows]
        if col not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
            logger.info(f"Migración: columna '{col}' añadida a '{table}'")
    except Exception as e:
        logger.warning(f"Migración de '{col}' en '{table}': {e}")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Migración automática de columnas nuevas (robustez ante BDs antiguas)
    with engine.begin() as conn:
        _add_column_if_missing(conn, "audios", "session_id",  "VARCHAR(64) DEFAULT ''")
        _add_column_if_missing(conn, "audios", "ui_language", "VARCHAR(8)  DEFAULT 'es'")
        _add_column_if_missing(conn, "audios", "user_id",     "VARCHAR(64)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
