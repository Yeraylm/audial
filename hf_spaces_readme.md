---
title: Audial Backend
emoji: 🎙
colorFrom: orange
colorTo: red
sdk: docker
pinned: false
app_port: 7860
---

# Audial Backend API

FastAPI backend for the Audial conversational audio analysis platform.

## Environment Variables (set in HF Spaces settings)

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for free LLM inference | Yes for LLM |
| `DATABASE_URL` | PostgreSQL URL (Supabase free tier) | Recommended |
| `WHISPER_MODEL` | `tiny` (default) or `base` | No |
| `VECTOR_BACKEND` | `chroma` (default) | No |

## Get free API keys

- **Groq** (LLM): https://console.groq.com — free, no credit card
- **Supabase** (DB): https://supabase.com — free 500 MB PostgreSQL
