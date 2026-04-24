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

> Transcribe, analiza y extrae conocimiento de tus audios con IA 100% local.

**Stack:** FastAPI · faster-whisper · Ollama (Llama 3 / Mistral / Qwen) · Chroma · Bootstrap 5

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

### Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
```

### Linux / macOS

```bash
bash scripts/install_linux.sh
```

### Arrancar

```powershell
# Windows
$env:PYTHONPATH = "E:\<ruta>\audial\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
```

```bash
# Linux/macOS
bash scripts/start.sh
```

Abre **http://localhost:8000**

---

## Configuración rápida (`.env`)

```env
WHISPER_MODEL=small          # tiny | base | small | medium
OLLAMA_MODEL=llama3:8b
WHISPER_LANGUAGE=            # vacío = auto-detect
DATABASE_URL=sqlite:///./data/platform.db
VECTOR_BACKEND=chroma
```

---

## Deploy online

### Frontend → Netlify

1. Conecta este repo en [netlify.com](https://netlify.com)
2. Build: `(none)` · Publish: `frontend`
3. Añade variable de entorno: `AUDIAL_API_URL=<url-del-backend>`

### Backend → Render

1. Conecta este repo en [render.com](https://render.com)
2. El archivo `render.yaml` configura todo automáticamente

> ⚠️ El tier gratuito de Render no incluye GPU. Usa `WHISPER_MODEL=tiny` y configura Ollama en una VM aparte o usa un proveedor cloud de LLM.

---

## Arquitectura Big Data (Medallion)

```
Audio (Bronze) → Transcripción + Diarización (Silver) → Análisis LLM (Gold)
```

- **Bronze:** archivos de audio + manifest parquet  
- **Silver:** transcripciones normalizadas con timestamps y hablantes  
- **Gold:** JSON estructurado con 14+ extracciones semánticas

---

## Licencia

MIT — Trabajo de Fin de Máster 2026.
