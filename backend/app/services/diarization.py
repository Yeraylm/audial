"""Diarizacion de hablantes.

Estrategia dual:
1. Resemblyzer (si disponible): embeddings de voz + clustering aglomerativo.
2. Fallback: heuristica de pausas — si la pausa entre segmentos supera el
   umbral, se considera un cambio de hablante. Produce SPEAKER_00 / SPEAKER_01
   alternados en puntos naturales de conversacion.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger

from app.services.transcription import TranscriptionSegment


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: str


# ------------------------------------------------------------------
# Fallback: deteccion por pausas
# ------------------------------------------------------------------
def _diarize_by_pauses(
    segments: list[TranscriptionSegment],
    pause_threshold: float = 1.2,
    max_speakers: int = 4,
) -> list[TranscriptionSegment]:
    """Alterna entre hablantes cuando hay una pausa larga entre segmentos."""
    if not segments:
        return segments

    speaker_id = 0
    prev_end   = segments[0].end

    for i, seg in enumerate(segments):
        if i == 0:
            seg.speaker = "SPEAKER_00"
        else:
            gap = seg.start - prev_end
            if gap >= pause_threshold:
                # Cambio de hablante en pausa larga
                speaker_id = (speaker_id + 1) % max(2, max_speakers)
            seg.speaker = f"SPEAKER_{speaker_id:02d}"
        prev_end = seg.end

    return segments


# ------------------------------------------------------------------
# Diarizacion principal
# ------------------------------------------------------------------
class DiarizationService:
    def __init__(self, max_speakers: int = 6) -> None:
        self.max_speakers = max_speakers
        self._encoder = None

    def _load_resemblyzer(self):
        if self._encoder is not None:
            return self._encoder
        try:
            from resemblyzer import VoiceEncoder
            self._encoder = VoiceEncoder("cpu")
            logger.info("Resemblyzer VoiceEncoder cargado (CPU)")
        except Exception as e:
            logger.warning(f"Resemblyzer no disponible ({e}); usando detección por pausas")
            self._encoder = False
        return self._encoder

    def diarize(
        self,
        audio_path: str | Path,
        segments: list[TranscriptionSegment],
    ) -> list[TranscriptionSegment]:
        encoder = self._load_resemblyzer()

        if not encoder:
            # Fallback: heuristica de pausas
            return _diarize_by_pauses(segments, pause_threshold=1.2,
                                       max_speakers=self.max_speakers)

        try:
            from resemblyzer import preprocess_wav
            from sklearn.cluster import AgglomerativeClustering

            wav = preprocess_wav(Path(audio_path))
            _, cont_embeds, wav_splits = encoder.embed_utterance(
                wav, return_partials=True, rate=1.3
            )

            n_speakers = self._estimate_n_speakers(cont_embeds)
            logger.info(f"Diarizacion Resemblyzer: {n_speakers} hablantes estimados")

            clustering = AgglomerativeClustering(n_clusters=n_speakers).fit(cont_embeds)
            labels     = clustering.labels_

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

        except Exception as e:
            logger.warning(f"Diarización Resemblyzer falló ({e}); usando pausas")
            return _diarize_by_pauses(segments, pause_threshold=1.2,
                                       max_speakers=self.max_speakers)

    def _estimate_n_speakers(self, embeds: np.ndarray) -> int:
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
        return max(2, min(int(np.argmin(ratio)) + 2, max_k))

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
