"""Diarizacion ligera de hablantes (CPU, sin token externo).

Estrategia en dos pasos:

1. Extraer embeddings de voz con Resemblyzer sobre ventanas de 1-2 segundos
   del audio.
2. Agrupar los embeddings con KMeans / clustering aglomerativo, limitando
   el numero de hablantes con una heuristica basada en el 'elbow' de la
   distancia al centroide.

Finalmente se mapean los segmentos de Whisper al hablante mas probable
segun el solapamiento temporal con los clusters. Si resemblyzer no esta
disponible se devuelve todo como 'SPEAKER_00' para no romper el pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from app.services.transcription import TranscriptionSegment


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


class DiarizationService:
    def __init__(self, max_speakers: int = 6) -> None:
        self.max_speakers = max_speakers
        self._encoder = None

    def _load(self):
        if self._encoder is not None:
            return self._encoder
        try:
            from resemblyzer import VoiceEncoder

            self._encoder = VoiceEncoder("cpu")
            logger.info("Resemblyzer VoiceEncoder cargado (CPU)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Resemblyzer no disponible ({e}); diarizacion desactivada")
            self._encoder = False
        return self._encoder

    def diarize(
        self,
        audio_path: str | Path,
        segments: list[TranscriptionSegment],
    ) -> list[TranscriptionSegment]:
        encoder = self._load()
        if not encoder:
            for s in segments:
                s.speaker = "SPEAKER_00"
            return segments

        try:
            from resemblyzer import preprocess_wav
            from sklearn.cluster import AgglomerativeClustering

            wav = preprocess_wav(Path(audio_path))
            _, cont_embeds, wav_splits = encoder.embed_utterance(  # type: ignore[union-attr]
                wav, return_partials=True, rate=1.3
            )

            n_speakers = self._estimate_n_speakers(cont_embeds)
            logger.info(f"Diarizacion: {n_speakers} hablantes estimados")

            clustering = AgglomerativeClustering(n_clusters=n_speakers).fit(cont_embeds)
            labels = clustering.labels_

            # Tiempos de cada ventana del encoder
            times = np.array(
                [[s.start, s.stop] for s in wav_splits], dtype=float
            ) / encoder.sampling_rate

            for seg in segments:
                mask = (times[:, 1] >= seg.start) & (times[:, 0] <= seg.end)
                if not mask.any():
                    seg.speaker = "SPEAKER_00"
                    continue
                lbl = int(np.bincount(labels[mask]).argmax())
                seg.speaker = f"SPEAKER_{lbl:02d}"
            return segments
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Diarizacion fallo ({e}); se usa un unico hablante")
            for s in segments:
                s.speaker = "SPEAKER_00"
            return segments

    def _estimate_n_speakers(self, embeds: np.ndarray) -> int:
        """Heuristica del codo sobre inercia KMeans."""
        from sklearn.cluster import KMeans

        max_k = min(self.max_speakers, max(2, len(embeds) // 3))
        if max_k < 2:
            return 1
        inertias = []
        for k in range(1, max_k + 1):
            km = KMeans(n_clusters=k, n_init=5, random_state=42).fit(embeds)
            inertias.append(km.inertia_)
        diffs = np.diff(inertias)
        if len(diffs) < 2:
            return 2
        ratio = diffs[1:] / (diffs[:-1] + 1e-9)
        elbow = int(np.argmin(ratio)) + 2
        return max(2, min(elbow, max_k))

    def summarize_turns(self, segments: list[TranscriptionSegment]) -> list[SpeakerTurn]:
        turns: list[SpeakerTurn] = []
        current: SpeakerTurn | None = None
        for s in segments:
            spk = s.speaker or "SPEAKER_00"
            if current is None or current.speaker != spk:
                if current:
                    turns.append(current)
                current = SpeakerTurn(start=s.start, end=s.end, speaker=spk)
            else:
                current.end = s.end
        if current:
            turns.append(current)
        return turns


diarization_service = DiarizationService()
