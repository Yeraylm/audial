"""Servicio de transcripcion local basado en faster-whisper.

faster-whisper usa CTranslate2 y puede ejecutarse en CPU (int8) con un
consumo de memoria muy inferior al whisper oficial. Devuelve texto,
segmentos con timestamps e idioma detectado.

Parametros optimizados para precision en CPU:
- beam_size=10: mejora significativa frente al default de 5.
- best_of=5: muestra multiples candidatos y elige el de mayor logprob.
- temperature fallback: reintenta con temperaturas crecientes si falla.
- condition_on_previous_text=True: mantiene contexto entre segmentos.
- vad_filter con min_silence 500ms: elimina silencios que confunden al modelo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None
    avg_logprob: float | None = None


@dataclass
class TranscriptionResult:
    full_text: str
    language: str
    duration: float
    segments: list[TranscriptionSegment] = field(default_factory=list)


class WhisperService:
    """Wrapper sobre faster-whisper con carga perezosa y parametros optimizados."""

    def __init__(self) -> None:
        self._model = None
        self._loaded_model_name: str | None = None

    def _load(self, model_name: str | None = None):
        target = model_name or settings.whisper_model
        if self._model is not None and self._loaded_model_name == target:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper no está instalado.\n"
                "Ejecuta: .venv\\Scripts\\pip.exe install faster-whisper"
            )

        logger.info(
            f"Cargando Whisper '{target}' "
            f"[{settings.whisper_device}/{settings.whisper_compute_type}]"
        )
        self._model = WhisperModel(
            target,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        self._loaded_model_name = target
        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        vad_filter: bool = True,
    ) -> TranscriptionResult:
        model = self._load()

        # None = autodetectar idioma (el modelo small hace esto muy bien)
        lang = language if language else settings.whisper_language
        logger.info(f"Transcribiendo {audio_path} (lang={lang or 'auto'})")

        segments_iter, info = model.transcribe(
            str(audio_path),
            language=lang,
            task="transcribe",
            # --- Precision ---
            beam_size=10,
            best_of=5,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            patience=1.0,
            length_penalty=1.0,
            repetition_penalty=1.0,
            no_repeat_ngram_size=0,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True,
            prompt_reset_on_temperature=0.5,
            initial_prompt=None,
            word_timestamps=False,
            # --- Filtrado VAD ---
            vad_filter=vad_filter,
            vad_parameters={
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 200,
            },
        )

        segments: list[TranscriptionSegment] = []
        full_parts: list[str] = []
        for seg in segments_iter:
            s = TranscriptionSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
                avg_logprob=getattr(seg, "avg_logprob", None),
            )
            segments.append(s)
            full_parts.append(s.text)

        logger.info(
            f"Transcripcion completada: idioma={info.language} "
            f"({info.language_probability:.0%}), {len(segments)} segmentos, "
            f"duracion={info.duration:.1f}s"
        )

        return TranscriptionResult(
            full_text=" ".join(full_parts).strip(),
            language=info.language,
            duration=float(info.duration),
            segments=segments,
        )

    def to_dict_segments(self, segments: list[TranscriptionSegment]) -> list[dict[str, Any]]:
        return [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "speaker": s.speaker,
            }
            for s in segments
        ]


whisper_service = WhisperService()
