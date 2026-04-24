"""Prompts de referencia para el LLM local.

El idioma de salida se controla SIEMPRE mediante la instruccion de idioma
que se antepone al system prompt. Asi, aunque el audio sea en ingles, si
el usuario tiene la UI en espanol todo el analisis saldrá en español, y
viceversa.

Se centralizan aqui para poder versionarlos, testearlos y traducirlos sin
tocar la logica. Cada prompt esta disenado para producir JSON estructurado
y aislado (una sola responsabilidad) para facilitar la robustez.
"""
from __future__ import annotations

SYSTEM_ANALYST_ES = (
    "Eres un analista experto en conversaciones humanas. Tu tarea es extraer "
    "informacion estructurada, precisa y no inventada a partir de una transcripcion. "
    "Si un campo no aparece, devuelve lista vacia o 'desconocido'. "
    "IMPORTANTE: responde SIEMPRE en ESPAÑOL, independientemente del idioma de la transcripcion."
)

SYSTEM_ANALYST_EN = (
    "You are an expert conversation analyst. Your task is to extract structured, "
    "accurate information from a transcription. If a field is not present, return "
    "an empty list or 'unknown'. "
    "IMPORTANT: always respond in ENGLISH, regardless of the language of the transcription."
)

def get_system_prompt(lang: str = "es") -> str:
    return SYSTEM_ANALYST_EN if lang.startswith("en") else SYSTEM_ANALYST_ES

# Keep backward compat alias
SYSTEM_ANALYST = SYSTEM_ANALYST_ES


SUMMARY_HIERARCHICAL = """Devuelve un JSON con tres niveles de resumen de la siguiente conversacion.

{{
  "tldr":   "una frase (max 25 palabras)",
  "medium": "parrafo de 4-6 lineas",
  "long":   "resumen estructurado con viñetas (8-15 lineas), cubriendo contexto, temas, decisiones y acciones"
}}

TRANSCRIPCION:
---
{text}
---
"""

ENTITIES_EXTRACTION = """Extrae las entidades de la siguiente transcripcion. Devuelve SOLO este JSON:

{{
  "personas":  [{{"name": "...", "role": "..."}}],
  "empresas":  ["..."],
  "lugares":   ["..."],
  "fechas":    ["..."],
  "productos": ["..."],
  "tareas":    ["..."]
}}

TRANSCRIPCION:
---
{text}
---
"""

INTENTS_DETECTION = """Clasifica las intenciones principales. Devuelve un array JSON con objetos:
{{ "intent": "peticion|acuerdo|queja|propuesta|pregunta|informacion|otro",
   "evidence": "cita breve",
   "confidence": 0.0-1.0 }}

TRANSCRIPCION:
---
{text}
---
"""

SEGMENTATION_TOPICS = """Divide la conversacion en temas coherentes. JSON:
[ {{ "topic": "titulo breve", "start_idx": int, "end_idx": int, "summary": "..." }} ]

La transcripcion viene numerada por segmentos. Usa los indices dados.

SEGMENTOS (idx|speaker|text):
---
{numbered}
---
"""

TIMELINE_EVENTS = """Construye una linea temporal de eventos clave. JSON:
[ {{ "time": "HH:MM:SS aprox", "event": "...", "speaker": "...", "importance": 1-5 }} ]

TRANSCRIPCION con timestamps:
---
{numbered}
---
"""

TASKS_EXTRACTION = """Extrae tareas accionables. JSON:
[ {{ "task": "...", "owner": "persona o 'desconocido'", "deadline": "fecha o null", "priority": "alta|media|baja" }} ]

TRANSCRIPCION:
---
{text}
---
"""

DECISIONS_EXTRACTION = """Extrae decisiones tomadas en la conversacion. JSON:
[ {{ "decision": "...", "made_by": "...", "rationale": "..." }} ]

TRANSCRIPCION:
---
{text}
---
"""

QUESTIONS_EXTRACTION = """Lista las preguntas relevantes formuladas, quien pregunta y si obtuvieron respuesta. JSON:
[ {{ "question": "...", "asked_by": "...", "answered": true|false, "answer_summary": "..." }} ]

TRANSCRIPCION:
---
{text}
---
"""

SENTIMENT_ANALYSIS = """Evalua sentimiento global y por hablante. JSON:
{{
  "global":   {{ "label": "positivo|neutro|negativo", "score": -1.0 a 1.0 }},
  "per_speaker": [ {{ "speaker": "...", "label": "...", "score": float }} ],
  "evolution": [ {{ "segment": int, "label": "...", "score": float }} ]
}}

SEGMENTOS (idx|speaker|text):
---
{numbered}
---
"""

CONFLICT_DETECTION = """Detecta discrepancias, tensiones o conflictos. JSON:
[ {{ "topic": "...", "parties": ["..."], "severity": 1-5, "evidence": "cita" }} ]

TRANSCRIPCION:
---
{text}
---
"""

CLEANING_TEXT = """Reescribe el siguiente texto eliminando muletillas ('eh', 'este', 'o sea', 'pues'...),
tartamudeos y repeticiones, manteniendo SIEMPRE el contenido original. No añadas informacion.
Devuelve unicamente el texto limpio, sin comentarios.

TEXTO:
---
{text}
---
"""

CHAT_RAG = """Eres un asistente que responde preguntas sobre una o varias conversaciones de audio
ya transcritas. Usa UNICAMENTE el CONTEXTO proporcionado. Si no hay informacion suficiente
responde 'No puedo responderlo con la informacion disponible'. Cita siempre el segmento
entre parentesis como (seg N).

PREGUNTA: {question}

CONTEXTO:
---
{context}
---

Respuesta:"""
