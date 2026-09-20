"""Lightweight FastEmbed embeddings for local semantic search."""

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
        from fastembed import TextEmbedding

        model_name = settings.EMBEDDING_MODEL

        # FastEmbed model name corresponding to the previous
        # sentence-transformers/all-MiniLM-L6-v2 model.
        if model_name == "sentence-transformers/all-MiniLM-L6-v2":
            model_name = "sentence-transformers/all-MiniLM-L6-v2"

        log.info("loading FastEmbed model %s", model_name)

        _model = TextEmbedding(model_name=model_name)

        # all-MiniLM-L6-v2 produces 384-dimensional vectors.
        _dim = 384

    return _model


def dimension() -> int:
    _load()
    return int(_dim or 384)


def embed_sync(texts: list[str]) -> list[list[float]]:
    model = _load()

    if not texts:
        return []

    vectors = model.embed(
        texts,
        batch_size=32,
    )

    return [vector.tolist() for vector in vectors]


async def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    return await asyncio.to_thread(embed_sync, texts)