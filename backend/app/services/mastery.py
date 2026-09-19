"""Evidence-based concept mastery with history. Never random, never static."""
from __future__ import annotations
from app.core.utils import clamp, new_id, now
from app.services import events

WEIGHT = {"easy": 0.15, "medium": 0.25, "hard": 0.35}
PRIOR = 0.5


def next_mastery(old: float | None, evidence_count: int, score: float, difficulty: str, kind: str) -> float:
    """EWMA whose step shrinks as evidence accumulates; harder / open-ended evidence moves it more.
    A correct hard answer lifts more than a correct easy one; a wrong easy answer hurts more than a wrong hard one."""
    base = WEIGHT.get(difficulty, 0.25)
    if kind == "open":
        base += 0.05
    if score < 0.5 and difficulty == "easy":
        base += 0.1
    if score >= 0.7 and difficulty == "hard":
        base += 0.05
    alpha = max(base, 1.0 / (evidence_count + 1))
    prev = PRIOR if old is None else old
    return clamp(prev + alpha * (score - prev))


async def apply_evidence(db, *, user_id: str, project_id: str, concept: str, score: float, difficulty: str, kind: str, source: str, ref_id: str) -> dict:
    cur = await db.mastery.find_one({"project_id": project_id, "concept": concept})
    old = cur["mastery"] if cur else None
    count = cur["evidence_count"] if cur else 0
    new = next_mastery(old, count, score, difficulty, kind)
    ts = now()
    await db.mastery.update_one({"project_id": project_id, "concept": concept}, {
        "$set": {"mastery": new, "evidence_count": count + 1, "last_assessed_at": ts, "last_score": score, "updated_at": ts},
        "$setOnInsert": {"_id": new_id(), "user_id": user_id, "created_at": ts}}, upsert=True)
    await db.mastery_history.insert_one({"_id": new_id(), "user_id": user_id, "project_id": project_id, "concept": concept,
                                         "mastery": new, "previous": old, "score": score, "difficulty": difficulty, "kind": kind,
                                         "source": source, "ref_id": ref_id, "created_at": ts})
    await events.record(db, user_id=user_id, type="mastery_updated", project_id=project_id,
                        payload={"concept": concept, "from": old, "to": new, "score": score}, dedupe_key=f"mu:{ref_id}")
    return {"concept": concept, "previous": old, "mastery": new}


async def snapshot(db, project_id: str) -> list[dict]:
    rows = await db.mastery.find({"project_id": project_id}).sort("mastery", 1).to_list(200)
    out = []
    for r in rows:
        hist = await db.mastery_history.find({"project_id": project_id, "concept": r["concept"]}).sort("created_at", -1).limit(6).to_list(6)
        mistakes = await db.quiz_answers.find({"project_id": project_id, "concept": r["concept"], "score": {"$lt": 0.5}}).sort("created_at", -1).limit(3).to_list(3)
        trend = "stable"
        if len(hist) >= 2:
            d = hist[0]["mastery"] - hist[-1]["mastery"]
            trend = "improving" if d > 0.05 else "declining" if d < -0.05 else "stable"
        out.append({"concept": r["concept"], "mastery": round(r["mastery"], 3), "evidence_count": r["evidence_count"],
                    "last_assessed_at": r.get("last_assessed_at"), "trend": trend,
                    "recent_mistakes": [{"question": m["question"], "at": m["created_at"]} for m in mistakes]})
    return out
