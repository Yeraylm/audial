# ============================================================
# Audial — Dockerfile para Hugging Face Spaces / Render / Railway
# Puerto: 7860 (HF Spaces) o $PORT (Render/Railway)
# ============================================================
FROM python:3.11-slim

# ffmpeg para conversión de audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libpq-dev gcc git && \
    rm -rf /var/lib/apt/lists/*

# Usuario no-root (HF Spaces lo requiere)
RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown -R user /app
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Dependencias Python
COPY --chown=user backend/requirements-minimal.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        faster-whisper \
        sentence-transformers \
        chromadb

# Código de la aplicación
COPY --chown=user backend/ ./backend/
COPY --chown=user frontend/ ./frontend/

# Directorios de datos
RUN mkdir -p data/audios data/transcripts data/exports data/embeddings

ENV PYTHONPATH=/app/backend
ENV WHISPER_MODEL=tiny
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8
ENV PORT=7860

EXPOSE 7860

CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
