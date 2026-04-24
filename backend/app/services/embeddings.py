"""Servicio de embeddings semanticos + vector store local (Chroma / FAISS)."""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger

from app.core.config import settings


@dataclass
class EmbeddingHit:
    audio_id: str
    segment_idx: int
    text: str
    score: float


class EmbeddingService:
    def __init__(self) -> None:
        self._model = None
        self._chroma = None
        self._faiss = None
        self._faiss_meta: list[dict] = []

    # --- modelo ---
    def _encoder(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Cargando modelo de embeddings: {settings.embedding_model}")
                self._model = SentenceTransformer(settings.embedding_model)
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers no esta instalado. "
                    "Ejecuta: .venv\\Scripts\\pip.exe install sentence-transformers"
                )
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._encoder().encode(texts, normalize_embeddings=True))

    # --- chroma ---
    def _chroma_client(self):
        if self._chroma is not None:
            return self._chroma
        try:
            import chromadb
            self._chroma = chromadb.PersistentClient(
                path=str(settings.embeddings_dir / "chroma")
            )
        except ImportError:
            raise RuntimeError(
                "chromadb no esta instalado. "
                "Ejecuta: .venv\\Scripts\\pip.exe install chromadb"
            )
        return self._chroma

    def _chroma_collection(self):
        client = self._chroma_client()
        return client.get_or_create_collection(
            "segments", metadata={"hnsw:space": "cosine"}
        )

    # --- faiss ---
    def _faiss_paths(self) -> tuple[Path, Path]:
        base = settings.embeddings_dir / "faiss"
        base.mkdir(parents=True, exist_ok=True)
        return base / "index.bin", base / "meta.pkl"

    def _faiss_load(self):
        import faiss
        idx_path, meta_path = self._faiss_paths()
        if self._faiss is None:
            if idx_path.exists() and meta_path.exists():
                self._faiss = faiss.read_index(str(idx_path))
                with meta_path.open("rb") as f:
                    self._faiss_meta = pickle.load(f)
            else:
                self._faiss = faiss.IndexFlatIP(384)
                self._faiss_meta = []
        return self._faiss

    def _faiss_persist(self):
        import faiss
        idx_path, meta_path = self._faiss_paths()
        faiss.write_index(self._faiss, str(idx_path))
        with meta_path.open("wb") as f:
            pickle.dump(self._faiss_meta, f)

    # --- API pública ---
    def add_segments(self, audio_id: str, segments: list[dict]) -> int:
        texts = [s["text"] for s in segments if s.get("text")]
        if not texts:
            return 0
        try:
            vectors = self.encode(texts)
        except Exception as e:
            logger.warning(f"No se pudieron calcular embeddings: {e}")
            return 0

        try:
            if settings.vector_backend == "chroma":
                col = self._chroma_collection()
                ids = [f"{audio_id}__{i}" for i in range(len(texts))]
                metas = [
                    {
                        "audio_id": audio_id,
                        "segment_idx": i,
                        "start": float(s.get("start", 0)),
                        "end":   float(s.get("end",   0)),
                    }
                    for i, s in enumerate(segments) if s.get("text")
                ]
                col.add(ids=ids, documents=texts, embeddings=vectors.tolist(), metadatas=metas)
            else:
                index = self._faiss_load()
                index.add(vectors.astype("float32"))
                for i, s in enumerate(segments):
                    self._faiss_meta.append(
                        {"audio_id": audio_id, "segment_idx": i, "text": s.get("text", "")}
                    )
                self._faiss_persist()
        except Exception as e:
            logger.error(f"Error indexando embeddings: {e}")
            return 0

        return len(texts)

    def search(
        self,
        query: str,
        top_k: int = 10,
        audio_id: str | None = None,
    ) -> list[EmbeddingHit]:
        try:
            qvec = self.encode([query])
        except Exception as e:
            logger.warning(f"No se pudo codificar la consulta: {e}")
            return []

        try:
            if settings.vector_backend == "chroma":
                col = self._chroma_collection()
                total = col.count()
                if total == 0:
                    return []
                n = min(top_k, total)
                kwargs: dict = {"query_embeddings": qvec.tolist(), "n_results": n}
                if audio_id:
                    kwargs["where"] = {"audio_id": audio_id}
                res = col.query(**kwargs)
                hits: list[EmbeddingHit] = []
                for doc, meta, dist in zip(
                    res["documents"][0], res["metadatas"][0], res["distances"][0]
                ):
                    hits.append(
                        EmbeddingHit(
                            audio_id=meta["audio_id"],
                            segment_idx=int(meta["segment_idx"]),
                            text=doc,
                            score=float(1.0 - dist),
                        )
                    )
                return hits

            # FAISS
            index = self._faiss_load()
            if index.ntotal == 0:
                return []
            scores, idxs = index.search(qvec.astype("float32"), min(top_k * 3, index.ntotal))
            hits = []
            for s, i in zip(scores[0], idxs[0]):
                if i < 0 or i >= len(self._faiss_meta):
                    continue
                meta = self._faiss_meta[i]
                if audio_id and meta["audio_id"] != audio_id:
                    continue
                hits.append(
                    EmbeddingHit(
                        audio_id=meta["audio_id"],
                        segment_idx=meta["segment_idx"],
                        text=meta["text"],
                        score=float(s),
                    )
                )
                if len(hits) >= top_k:
                    break
            return hits

        except Exception as e:
            logger.error(f"Error en busqueda vectorial: {e}")
            return []


embedding_service = EmbeddingService()
