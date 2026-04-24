"""Configuracion central del sistema.

Centraliza variables de entorno, rutas y parametros de modelos para que
cualquier cambio (host de Ollama, modelo LLM, motor de embeddings, etc.)
sea un cambio de una sola linea.
"""
from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2].parent  # e:/TFM
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "Plataforma IA Conversacional - TFM"
    environment: str = os.getenv("ENV", "local")
    debug: bool = True

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Directories ---
    data_dir: Path = DATA_DIR
    audio_dir: Path = DATA_DIR / "audios"
    transcript_dir: Path = DATA_DIR / "transcripts"
    export_dir: Path = DATA_DIR / "exports"
    embeddings_dir: Path = DATA_DIR / "embeddings"

    # --- Database ---
    # Por defecto SQLite para que funcione sin instalar nada mas.
    # En produccion basta con cambiar a postgresql://user:pass@host:5432/db
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(DATA_DIR / 'platform.db').as_posix()}",
    )

    # --- Whisper (faster-whisper) ---
    # 'small' ofrece mucha mejor precisión que 'base' en CPU.
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")  # tiny|base|small|medium
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    # None = detección automática de idioma. 'es' o 'en' para forzar.
    whisper_language: str | None = os.getenv("WHISPER_LANGUAGE") or None

    # --- LLM (Groq cloud gratis o Ollama local) ---
    # Si GROQ_API_KEY tiene valor, se usa Groq. Si no, Ollama.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3:8b")
    ollama_fallback_models: list[str] = ["mistral:7b", "qwen2.5:7b-instruct"]
    ollama_timeout: int = 180

    # --- Embeddings ---
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    vector_backend: str = os.getenv("VECTOR_BACKEND", "chroma")  # chroma|faiss

    # --- Limits ---
    max_audio_mb: int = 200
    chunk_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Asegurar directorios
for _d in (
    settings.data_dir,
    settings.audio_dir,
    settings.transcript_dir,
    settings.export_dir,
    settings.embeddings_dir,
):
    _d.mkdir(parents=True, exist_ok=True)
