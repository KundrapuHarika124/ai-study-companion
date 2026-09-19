"""Project-scoped retrieval + evidence sufficiency."""
from __future__ import annotations
from dataclasses import dataclass
from app.core.config import settings
from app.services import embeddings, vectorstore


@dataclass
class Evidence:
    chunk_id: str
    material_id: str
    title: str
    page: int
    heading: str
    text: str
    score: float
    type: str
    concepts: list[str]

    @property
    def label(self) -> str:
        return f"{self.title} — Page {self.page}"


async def retrieve(*, user_id: str, project_id: str, query: str, limit: int = 8, types: tuple[str, ...] = ("text",)) -> list[Evidence]:
    [vec] = await embeddings.embed([query])
    hits = []
    for t in types:
        hits += vectorstore.search(vec, user_id=user_id, project_id=project_id, limit=limit, extra={"type": t})
    hits.sort(key=lambda h: h.score, reverse=True)
    out = []
    for h in hits[:limit]:
        p = h.payload
        if p.get("project_id") != project_id or p.get("user_id") != user_id:
            continue  # defense in depth: never leak across projects even if a filter were misconfigured
        out.append(Evidence(chunk_id=p["chunk_id"], material_id=p["material_id"], title=p.get("title", "Material"),
                            page=int(p.get("page", 0)), heading=p.get("heading", ""), text=p.get("text", ""), score=h.score,
                            type=p.get("type", "text"), concepts=p.get("concepts", [])))
    return out


def sufficient(evidence: list[Evidence]) -> bool:
    """Cheap pre-check before spending an LLM call. The model also judges sufficiency on the retrieved text."""
    if not evidence:
        return False
    top = evidence[0].score
    return top >= settings.RETRIEVAL_MIN_SCORE
