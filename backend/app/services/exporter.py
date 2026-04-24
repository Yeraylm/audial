"""Exportacion de analisis a PDF y JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


def export_json(audio_id: str, payload: dict[str, Any]) -> Path:
    path = settings.export_dir / f"{audio_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def export_pdf(audio_id: str, payload: dict[str, Any]) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    path = settings.export_dir / f"{audio_id}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story: list[Any] = []
    story.append(Paragraph(f"Analisis de conversacion {audio_id[:8]}", styles["Title"]))
    story.append(Spacer(1, 12))

    def _section(title: str, content: Any) -> None:
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        for line in str(content).split("\n"):
            story.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), styles["BodyText"]))
        story.append(Spacer(1, 10))

    _section("Resumen corto", payload.get("summary_short", ""))
    _section("Resumen medio", payload.get("summary_medium", ""))
    _section("Resumen extenso", payload.get("summary_long", ""))
    _section("Entidades", payload.get("entities", {}))
    _section("Tareas", payload.get("tasks", []))
    _section("Decisiones", payload.get("decisions", []))
    _section("Preguntas", payload.get("questions", []))
    _section("Sentimiento", payload.get("sentiment", {}))
    _section("Conflictos", payload.get("conflicts", []))
    _section("Metricas", payload.get("metrics", {}))

    doc.build(story)
    return path
