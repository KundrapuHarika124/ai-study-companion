"""Local sentence-transformers embeddings (no external API cost)."""
from __future__ import annotations
import asyncio
import logging
from app.core.config import settings

log = logging.getLogger("embeddings")
_model = None
_dim: int | None = None


def _load():
    global _model, _dim
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("loading embedding model %s", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        _dim = _model.get_sentence_embedding_dimension()
    return _model


def dimension() -> int:
    _load()
    return int(_dim or 384)


def embed_sync(texts: list[str]) -> list[list[float]]:
    m = _load()
    vecs = m.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vecs]


async def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(embed_sync, texts)
