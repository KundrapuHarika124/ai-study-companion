"""Qdrant access. Every search is filtered by user_id + project_id: no global retrieval, ever."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from app.core.config import settings

log = logging.getLogger("qdrant")
_client = None


def client():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=20)
    return _client


def ensure_collection(dim: int) -> None:
    from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
    c = client()
    names = {col.name for col in c.get_collections().collections}
    if settings.QDRANT_COLLECTION not in names:
        c.create_collection(settings.QDRANT_COLLECTION, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        for field in ("user_id", "project_id", "material_id", "type"):
            c.create_payload_index(settings.QDRANT_COLLECTION, field_name=field, field_schema=PayloadSchemaType.KEYWORD)


def project_filter(user_id: str, project_id: str, extra: dict | None = None):
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    must = [FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    for k, v in (extra or {}).items():
        must.append(FieldCondition(key=k, match=MatchValue(value=v)))
    return Filter(must=must)


def upsert(points: list[dict]) -> None:
    """points: [{id, vector, payload}]"""
    from qdrant_client.models import PointStruct
    if not points:
        return
    c = client()
    for i in range(0, len(points), 128):
        batch = [PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points[i:i + 128]]
        c.upsert(settings.QDRANT_COLLECTION, points=batch, wait=True)


@dataclass
class Hit:
    chunk_id: str
    score: float
    payload: dict


def search(vector: list[float], *, user_id: str, project_id: str, limit: int = 8, extra: dict | None = None) -> list[Hit]:
    c = client()
    res = c.query_points(settings.QDRANT_COLLECTION, query=vector, query_filter=project_filter(user_id, project_id, extra),
                         limit=limit, with_payload=True)
    return [Hit(chunk_id=p.payload.get("chunk_id", str(p.id)), score=float(p.score), payload=p.payload or {}) for p in res.points]


def delete_material(material_id: str) -> None:
    from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
    client().delete(settings.QDRANT_COLLECTION, points_selector=FilterSelector(
        filter=Filter(must=[FieldCondition(key="material_id", match=MatchValue(value=material_id))])))


def healthy() -> bool:
    try:
        client().get_collections()
        return True
    except Exception:  # noqa: BLE001
        return False
