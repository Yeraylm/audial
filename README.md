---
title: Audial Backend
emoji: 🎙
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
app_port: 7860
---

# Audial — Plataforma IA Conversacional

> Transcribe, analiza y extrae conocimiento de tus audios con IA 100% local o en cloud gratuito.

**Stack:** FastAPI · faster-whisper · Groq (Llama 3.3 70B) / Ollama · Chroma · Bootstrap 5

---

## Variables de entorno requeridas (HF Spaces → Settings → Variables)

| Variable | Descripción |
|----------|-------------|
| `GROQ_API_KEY` | API key de [Groq](https://console.groq.com) (gratis) |
| `DATABASE_URL` | URL PostgreSQL de [Supabase](https://supabase.com) (gratis) |
| `WHISPER_MODEL` | `tiny` (por defecto en cloud) |

---

## Características

| Módulo | Descripción |
|--------|-------------|
| 🎙 Transcripción | faster-whisper (CPU int8) con timestamps y VAD |
| 👥 Diarización | Resemblyzer + clustering aglomerativo |
| 🧠 Análisis LLM | 14+ extracciones: resumen, entidades, tareas, decisiones… |
| 🌐 Multiidioma | UI en ES/EN; el LLM responde en el idioma de la interfaz |
| 🔍 RAG | Embeddings multilingües (Chroma/FAISS) + asistente conversacional |
| 📊 Dashboard | KPIs, gráficas de sentimiento, audios relacionados |
| 👤 Multi-usuario | Aislamiento por session-id (localStorage) sin login |

---

## Instalación local

```powershell
# Windows
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
$env:PYTHONPATH = "E:\<ruta>\audial\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
```

```bash
# Linux/macOS
bash scripts/install_linux.sh && bash scripts/start.sh
```

---

## Deploy gratuito

- **Frontend** → [Netlify](https://netlify.com) (directorio `frontend/`)
- **Backend** → Hugging Face Spaces (este Space)
- **LLM** → [Groq API](https://console.groq.com) — Llama 3.3 70B gratis
- **BD** → [Supabase](https://supabase.com) — PostgreSQL 500 MB gratis

---

## Arquitectura Big Data (Medallion)

```
Audio (Bronze) → Transcripción + Diarización (Silver) → Análisis LLM (Gold)
```

MIT — TFM 2026
