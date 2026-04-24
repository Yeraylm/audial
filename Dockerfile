# ============================================================
# Audial — Docker image for Hugging Face Spaces
# Compatible with Render, Railway, Fly.io, HF Spaces
# ============================================================
FROM python:3.11-slim

# System deps: ffmpeg for audio conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY backend/requirements-minimal.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir faster-whisper sentence-transformers chromadb

# Copy project
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/.gitkeep ./data/.gitkeep

# Ensure data dirs exist
RUN mkdir -p data/audios data/transcripts data/exports data/embeddings

# HF Spaces runs as non-root on port 7860
ENV PORT=7860
ENV PYTHONPATH=/app/backend
ENV WHISPER_MODEL=tiny
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

EXPOSE 7860

# HF Spaces expects the app to listen on $PORT
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1
