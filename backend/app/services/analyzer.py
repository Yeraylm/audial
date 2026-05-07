"""Orquestador de analisis IA.

El idioma de salida (output_lang) controla el idioma del LLM:
- "es" → todo en español
- "en" → everything in English
Esto es independiente del idioma del audio (que solo afecta a Whisper).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any

from loguru import logger

from app.services.llm_service import llm
from app.services.prompts import (
    CLEANING_TEXT,
    CONFLICT_DETECTION,
    DECISIONS_EXTRACTION,
    ENTITIES_EXTRACTION,
    ENTITIES_EXTRACTION_EN,
    INTENTS_DETECTION,
    QUESTIONS_EXTRACTION,
    SEGMENTATION_TOPICS,
    SENTIMENT_ANALYSIS,
    SUMMARY_HIERARCHICAL,
    TASKS_EXTRACTION,
    TIMELINE_EVENTS,
    get_system_prompt,
)


# ── helpers ──────────────────────────────────────────────────────────
def _fmt_time(t: float) -> str:
    h, m, s = int(t // 3600), int((t % 3600) // 60), int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _number_segments(segments: list[dict]) -> str:
    return "\n".join(
        f"{i}|{_fmt_time(s.get('start', 0))}|{s.get('speaker') or 'SPEAKER_00'}|{s.get('text', '').strip()}"
        for i, s in enumerate(segments)
    )


def _chunk_text(text: str, max_chars: int = 6000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = re.split(r"(?<=[\.\!\?])\s+", text)
    chunks, buf = [], ""
    for p in paragraphs:
        if len(buf) + len(p) < max_chars:
            buf += (" " if buf else "") + p
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks


# ── componentes individuales ──────────────────────────────────────────
def clean_text(text: str, lang: str = "es") -> str:
    if not text:
        return ""
    try:
        cleaned = llm.complete(CLEANING_TEXT.format(text=text[:8000]),
                               temperature=0.0,
                               system=get_system_prompt(lang))
        if cleaned:
            return cleaned.strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Limpieza LLM fallo: {e}")
    patterns = [r"\b(eh+|um+|uh+|like|you know|este|o sea|pues|bueno|digamos|vale|mmm+)\b"]
    out = text
    for p in patterns:
        out = re.sub(p, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


def hierarchical_summary(text: str, lang: str = "es") -> dict[str, str]:
    sys = get_system_prompt(lang)
    if not text.strip():
        return {"tldr": "", "medium": "", "long": ""}
    chunks = _chunk_text(text, 6000)
    if len(chunks) == 1:
        data = llm.complete_json(SUMMARY_HIERARCHICAL.format(text=chunks[0]), system=sys)
        if isinstance(data, dict):
            return {"tldr": data.get("tldr", ""), "medium": data.get("medium", ""), "long": data.get("long", "")}
        return {"tldr": "", "medium": "", "long": ""}
    partials = []
    for c in chunks:
        d = llm.complete_json(SUMMARY_HIERARCHICAL.format(text=c), system=sys)
        if isinstance(d, dict):
            partials.append(d.get("medium", ""))
    merged = "\n\n".join(partials)
    data = llm.complete_json(SUMMARY_HIERARCHICAL.format(text=merged[:8000]), system=sys)
    if isinstance(data, dict):
        return {"tldr": data.get("tldr", ""), "medium": data.get("medium", ""), "long": data.get("long", "")}
    return {"tldr": "", "medium": merged[:800], "long": merged}


def extract_entities(text: str, lang: str = "es") -> dict[str, Any]:
    prompt = ENTITIES_EXTRACTION_EN if lang.startswith("en") else ENTITIES_EXTRACTION
    data = llm.complete_json(prompt.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, dict) else {}


def detect_intents(text: str, lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(INTENTS_DETECTION.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, list) else []


def segment_topics(segments: list[dict], lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(SEGMENTATION_TOPICS.format(numbered=_number_segments(segments)[:8000]),
                             system=get_system_prompt(lang))
    if isinstance(data, list) and data:
        return data
    # Fallback: un tema general cubriendo todos los segmentos
    if segments:
        summary = " ".join(s.get("text", "") for s in segments[:4]).strip()[:200]
        label = "General" if lang.startswith("en") else "General"
        return [{"topic": label, "start_idx": 0, "end_idx": len(segments) - 1, "summary": summary}]
    return []


def build_timeline(segments: list[dict], lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(TIMELINE_EVENTS.format(numbered=_number_segments(segments)[:8000]),
                             system=get_system_prompt(lang))
    if isinstance(data, list) and data:
        return data
    # Fallback: surface first, middle, and last segments as timeline anchors
    if not segments:
        return []
    idxs = sorted(set([0, len(segments) // 2, len(segments) - 1]))
    return [
        {
            "time": _fmt_time(segments[i].get("start", 0)),
            "event": (segments[i].get("text") or "").strip()[:120],
            "speaker": segments[i].get("speaker") or "SPEAKER_00",
            "importance": 3 if i == len(segments) // 2 else 2,
        }
        for i in idxs
        if (segments[i].get("text") or "").strip()
    ]


def extract_tasks(text: str, lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(TASKS_EXTRACTION.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, list) else []


def extract_decisions(text: str, lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(DECISIONS_EXTRACTION.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, list) else []


def extract_questions(text: str, lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(QUESTIONS_EXTRACTION.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, list) else []


def analyze_sentiment(segments: list[dict], lang: str = "es") -> dict[str, Any]:
    data = llm.complete_json(SENTIMENT_ANALYSIS.format(numbered=_number_segments(segments)[:8000]),
                             system=get_system_prompt(lang))
    if not isinstance(data, dict):
        data = {}

    default_label = "neutral" if lang.startswith("en") else "neutro"
    if "global" not in data or not isinstance(data.get("global"), dict):
        data["global"] = {"label": default_label, "score": 0.0}

    global_score = float(data["global"].get("score") or 0.0)

    # Fallback: generate evolution from each segment if LLM didn't provide it
    if not data.get("evolution") and segments:
        data["evolution"] = [
            {"segment": i, "score": global_score}
            for i in range(len(segments))
        ]

    # Fallback: generate per_speaker if LLM didn't provide it
    if not data.get("per_speaker") and segments:
        speakers = list(dict.fromkeys(s.get("speaker") or "SPEAKER_00" for s in segments))
        data["per_speaker"] = [{"speaker": spk, "score": global_score} for spk in speakers]

    return data


def detect_conflicts(text: str, lang: str = "es") -> list[dict[str, Any]]:
    data = llm.complete_json(CONFLICT_DETECTION.format(text=text[:8000]), system=get_system_prompt(lang))
    return data if isinstance(data, list) else []


def conversation_metrics(segments: list[dict]) -> dict[str, Any]:
    if not segments:
        return {}
    durations = [s["end"] - s["start"] for s in segments]
    total = max(sum(durations), 0.001)
    speakers = [s.get("speaker") or "SPK" for s in segments]
    per_speaker: Counter = Counter()
    words_per_speaker: Counter = Counter()
    for s, spk in zip(segments, speakers):
        per_speaker[spk] += s["end"] - s["start"]
        words_per_speaker[spk] += len(s["text"].split())
    participation = {spk: round(100 * t / total, 2) for spk, t in per_speaker.items()}
    return {
        "total_duration_sec": round(total, 2),
        "num_segments": len(segments),
        "num_speakers": len(set(speakers)),
        "participation_pct": participation,
        "words_per_speaker": dict(words_per_speaker),
        "avg_segment_sec": round(statistics.mean(durations), 2),
        "words_per_minute": round(sum(words_per_speaker.values()) / (total / 60), 1),
    }


def run_full_analysis(full_text: str, segments: list[dict], output_lang: str = "es") -> dict[str, Any]:
    """Ejecuta todas las extracciones usando el idioma de output indicado."""
    logger.info(f"Lanzando analisis IA completo (output_lang={output_lang})")
    return {
        "summary":   hierarchical_summary(full_text, output_lang),
        "entities":  extract_entities(full_text, output_lang),
        "tasks":     extract_tasks(full_text, output_lang),
        "decisions": extract_decisions(full_text, output_lang),
        "questions": extract_questions(full_text, output_lang),
        "topics":    segment_topics(segments, output_lang),
        "timeline":  build_timeline(segments, output_lang),
        "intents":   detect_intents(full_text, output_lang),
        "sentiment": analyze_sentiment(segments, output_lang),
        "conflicts": detect_conflicts(full_text, output_lang),
        "metrics":   conversation_metrics(segments),
    }
