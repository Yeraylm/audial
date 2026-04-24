"""Pipeline ETL (Big Data) — arquitectura Bronze/Silver/Gold.

Robustez añadida:
- _update_job hace rollback antes de cada commit para recuperarse de sesiones
  en estado de error (ej. fallo en commit anterior).
- _safe_dict / _safe_list normalizan cualquier salida del LLM antes de
  asignarla a las columnas JSON, evitando el error 'type list is not
  supported' de SQLite cuando el modelo devuelve un tipo inesperado.
"""
from __future__ import annotations

import datetime as dt
import json
import multiprocessing as mp
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from app.core.config import settings
from app.models import Analysis, Audio, Job, JobStatus, SessionLocal, Transcript, init_db
from app.services.analyzer import clean_text, run_full_analysis
from app.services.diarization import diarization_service
from app.services.embeddings import embedding_service
from app.services.transcription import whisper_service


@dataclass
class PipelineResult:
    audio_id: str
    transcript_ok: bool = False
    analysis_ok: bool = False
    embedded_segments: int = 0
    errors: list[str] = field(default_factory=list)


# ------------------------------------------------------------------
# Helpers de normalización JSON
# ------------------------------------------------------------------
def _safe_dict(val: Any, wrap_key: str | None = None) -> dict:
    """Garantiza que val sea un dict. Si viene como list, lo envuelve."""
    if isinstance(val, dict):
        return val
    if isinstance(val, list):
        return {wrap_key: val} if wrap_key else {"items": val}
    return {}


def _safe_list(val: Any) -> list:
    """Garantiza que val sea una list."""
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        # LLM devolvió {items: [...]} o similar
        for k in ("items", "data", "results"):
            if k in val and isinstance(val[k], list):
                return val[k]
        return list(val.values()) if val else []
    return []


def _clean_json(val: Any) -> Any:
    """Fuerza serialización/deserialización para limpiar tipos no soportados."""
    try:
        return json.loads(json.dumps(val, ensure_ascii=False))
    except (TypeError, ValueError):
        return {}


# ------------------------------------------------------------------
# Pipeline principal
# ------------------------------------------------------------------
def process_single_audio(
    audio_id: str,
    enable_diarization: bool = True,
    language: str | None = None,
    output_lang: str = "es",
) -> PipelineResult:
    init_db()
    db = SessionLocal()
    result = PipelineResult(audio_id=audio_id)
    job = None

    try:
        audio = db.query(Audio).filter(Audio.id == audio_id).first()
        if not audio:
            raise RuntimeError(f"Audio {audio_id} no encontrado en BD")

        job = db.query(Job).filter(Job.audio_id == audio_id).order_by(Job.id.desc()).first()
        if not job:
            job = Job(audio_id=audio_id)
            db.add(job)
            db.commit()

        # ---- Bronze → Silver: transcripción ----
        _update_job(db, job, JobStatus.RUNNING, "transcription", 0.1, "Transcribiendo audio")
        logger.info(f"[{audio_id[:8]}] Iniciando transcripción (lang={language or 'auto'})")

        tr = whisper_service.transcribe(audio.filepath, language=language)
        audio.duration_sec = tr.duration
        segments = tr.segments

        # ---- Diarización ----
        if enable_diarization:
            _update_job(db, job, JobStatus.RUNNING, "diarization", 0.35, "Identificando hablantes")
            try:
                segments = diarization_service.diarize(audio.filepath, segments)
            except Exception as e:
                logger.warning(f"[{audio_id[:8]}] Diarización omitida: {e}")

        cleaned = clean_text(tr.full_text)
        seg_dicts = whisper_service.to_dict_segments(segments)
        logger.info(f"[{audio_id[:8]}] Transcripción OK — {len(seg_dicts)} segmentos, lang={tr.language}")

        existing_t = db.query(Transcript).filter(Transcript.audio_id == audio_id).first()
        if existing_t:
            existing_t.full_text = tr.full_text
            existing_t.cleaned_text = cleaned
            existing_t.segments_json = {"segments": seg_dicts}
            existing_t.language = tr.language
        else:
            db.add(Transcript(
                audio_id=audio_id,
                language=tr.language,
                full_text=tr.full_text,
                cleaned_text=cleaned,
                segments_json={"segments": seg_dicts},
            ))
        db.commit()
        result.transcript_ok = True

        # ---- Silver → Gold: análisis LLM ----
        # Obtener ui_language del registro de audio si no se pasó explícitamente
        if output_lang == "es":
            db.refresh(audio)
            output_lang = getattr(audio, "ui_language", "es") or "es"

        _update_job(db, job, JobStatus.RUNNING, "llm_analysis", 0.55, "Analizando con LLM local")
        logger.info(f"[{audio_id[:8]}] Lanzando análisis IA (output_lang={output_lang})")

        analysis = run_full_analysis(cleaned or tr.full_text, seg_dicts, output_lang=output_lang)
        logger.info(f"[{audio_id[:8]}] Análisis IA completado")

        # Normalizar todos los valores antes de guardar en SQLite
        entities_raw = analysis.get("entities", {})
        entities_val = _clean_json(entities_raw if isinstance(entities_raw, dict) else {"items": _safe_list(entities_raw)})

        a = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
        is_new = a is None
        if is_new:
            a = Analysis(audio_id=audio_id)

        a.summary_short  = str(analysis.get("summary", {}).get("tldr", ""))
        a.summary_medium = str(analysis.get("summary", {}).get("medium", ""))
        a.summary_long   = str(analysis.get("summary", {}).get("long", ""))
        a.entities        = entities_val
        a.tasks           = {"items": _safe_list(analysis.get("tasks", []))}
        a.decisions       = {"items": _safe_list(analysis.get("decisions", []))}
        a.questions       = {"items": _safe_list(analysis.get("questions", []))}
        a.topics          = {"items": _safe_list(analysis.get("topics", []))}
        a.timeline        = {"items": _safe_list(analysis.get("timeline", []))}
        a.intents         = {"items": _safe_list(analysis.get("intents", []))}
        a.sentiment       = _clean_json(_safe_dict(analysis.get("sentiment", {})))
        a.conflicts       = {"items": _safe_list(analysis.get("conflicts", []))}
        a.metrics         = _clean_json(_safe_dict(analysis.get("metrics", {})))

        if is_new:
            db.add(a)
        db.commit()
        result.analysis_ok = True
        logger.info(f"[{audio_id[:8]}] Analysis guardado en BD")

        # ---- Indexación vectorial ----
        _update_job(db, job, JobStatus.RUNNING, "embeddings", 0.85, "Indexando embeddings")
        try:
            result.embedded_segments = embedding_service.add_segments(audio_id, seg_dicts)
            logger.info(f"[{audio_id[:8]}] {result.embedded_segments} segmentos indexados")
        except Exception as e:
            logger.warning(f"[{audio_id[:8]}] Embeddings omitidos: {e}")

        _update_job(db, job, JobStatus.DONE, "done", 1.0, "Procesamiento completo")
        logger.info(f"[{audio_id[:8]}] Pipeline finalizado correctamente")

    except Exception as e:
        logger.exception(f"[{audio_id[:8]}] Fallo el pipeline")
        result.errors.append(str(e))
        if job is not None:
            try:
                # Rollback explícito para recuperar la sesión
                db.rollback()
                job.status   = JobStatus.FAILED
                job.stage    = "error"
                job.progress = 1.0
                job.message  = str(e)[:500]
                job.finished_at = dt.datetime.utcnow()
                db.commit()
            except Exception as inner:
                logger.error(f"[{audio_id[:8]}] No se pudo marcar job como FAILED: {inner}")
    finally:
        db.close()
    return result


def _update_job(db, job, status: JobStatus, stage: str, progress: float, msg: str) -> None:
    """Actualiza el estado del job con rollback previo para sesiones en error."""
    try:
        db.rollback()  # limpiar cualquier transacción pendiente/fallida
        job.status   = status
        job.stage    = stage
        job.progress = progress
        job.message  = msg
        if status == JobStatus.RUNNING and job.started_at is None:
            job.started_at = dt.datetime.utcnow()
        if status in (JobStatus.DONE, JobStatus.FAILED):
            job.finished_at = dt.datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"_update_job falló ({stage}): {e}")


# ------------------------------------------------------------------
# Batch / ETL masivo
# ------------------------------------------------------------------
def register_audio_file(path: Path) -> str:
    init_db()
    db = SessionLocal()
    try:
        audio = Audio(
            filename=path.name,
            filepath=str(path),
            size_bytes=path.stat().st_size,
            mime_type=f"audio/{path.suffix.lstrip('.') or 'mpeg'}",
        )
        db.add(audio)
        db.commit()
        db.refresh(audio)
        return audio.id
    finally:
        db.close()


def run_batch(folder: Path, workers: int = 2) -> pd.DataFrame:
    audio_paths = [
        p for p in folder.rglob("*")
        if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
    ]
    if not audio_paths:
        logger.warning(f"No se encontraron audios en {folder}")
        return pd.DataFrame()

    manifest = []
    for p in audio_paths:
        aid = register_audio_file(p)
        manifest.append({"audio_id": aid, "path": str(p), "size": p.stat().st_size})
    df = pd.DataFrame(manifest)

    bronze = settings.data_dir / "bronze"
    bronze.mkdir(exist_ok=True)
    df.to_parquet(bronze / f"manifest_{dt.datetime.now():%Y%m%d_%H%M%S}.parquet", index=False)

    _run_parallel_local(df["audio_id"].tolist(), workers)
    return df


def _run_parallel_local(audio_ids: list[str], workers: int) -> None:
    if workers <= 1:
        for aid in audio_ids:
            process_single_audio(aid)
        return
    with mp.get_context("spawn").Pool(processes=workers) as pool:
        pool.map(process_single_audio, audio_ids)


def export_gold_layer() -> Path:
    init_db()
    db = SessionLocal()
    try:
        rows = []
        for a in db.query(Analysis).all():
            rows.append({
                "audio_id":        a.audio_id,
                "summary_short":   a.summary_short,
                "sentiment_label": (a.sentiment or {}).get("global", {}).get("label"),
                "sentiment_score": (a.sentiment or {}).get("global", {}).get("score"),
                "num_tasks":       len((a.tasks or {}).get("items", [])),
                "num_decisions":   len((a.decisions or {}).get("items", [])),
                "num_conflicts":   len((a.conflicts or {}).get("items", [])),
                "duration_sec":    (a.metrics or {}).get("total_duration_sec"),
                "num_speakers":    (a.metrics or {}).get("num_speakers"),
            })
        df = pd.DataFrame(rows)
        gold = settings.data_dir / "gold"
        gold.mkdir(exist_ok=True)
        out = gold / f"analysis_{dt.datetime.now():%Y%m%d_%H%M%S}.parquet"
        df.to_parquet(out, index=False)
        return out
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline ETL del sistema TFM")
    parser.add_argument("--batch", type=str)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--export-gold", action="store_true")
    args = parser.parse_args()
    if args.batch:
        df = run_batch(Path(args.batch), workers=args.workers)
        print(json.dumps({"ingested": len(df)}, indent=2))
    if args.export_gold:
        p = export_gold_layer()
        print(f"Gold parquet -> {p}")
