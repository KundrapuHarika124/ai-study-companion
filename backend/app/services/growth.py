"""Growth analysis from mastery history: improving / stable / needs attention. Honest empty states when evidence is thin."""
from __future__ import annotations
from datetime import timedelta
from app.core.utils import now


def classify(history: list[dict], current: float, evidence_count: int) -> str:
    """history sorted ascending by time (within the window)."""
    if evidence_count < 2 or len(history) < 2:
        return "insufficient_evidence"
    delta = history[-1]["mastery"] - history[0]["mastery"]
    if delta >= 0.08:
        return "improving"
    if delta <= -0.06 or current < 0.5:
        return "attention"
    return "stable"


async def analyze(db, project_id: str, days: int = 30) -> dict:
    since = now() - timedelta(days=days)
    rows = await db.mastery.find({"project_id": project_id}).to_list(200)
    concepts = []
    for r in rows:
        hist = await db.mastery_history.find({"project_id": project_id, "concept": r["concept"], "created_at": {"$gte": since}}).sort("created_at", 1).to_list(200)
        status = classify(hist, r["mastery"], r["evidence_count"])
        concepts.append({"concept": r["concept"], "mastery": round(r["mastery"], 3), "status": status, "evidence_count": r["evidence_count"],
                         "delta": round((hist[-1]["mastery"] - hist[0]["mastery"]), 3) if len(hist) >= 2 else None,
                         "series": [{"t": h["created_at"], "v": round(h["mastery"], 3)} for h in hist]})
    concepts.sort(key=lambda c: ({"attention": 0, "improving": 1, "stable": 2, "insufficient_evidence": 3}[c["status"]], c["mastery"]))
    counts = {k: sum(1 for c in concepts if c["status"] == k) for k in ("improving", "stable", "attention", "insufficient_evidence")}
    # session performance trend
    sessions = await db.quiz_sessions.find({"project_id": project_id, "status": "completed"}).sort("finished_at", 1).limit(50).to_list(50)
    perf = [{"t": s["finished_at"], "avg": round(s["score_sum"] / max(1, s["answered"]), 3), "n": s["answered"]} for s in sessions]
    return {"concepts": concepts, "counts": counts, "session_performance": perf, "has_evidence": any(c["status"] != "insufficient_evidence" for c in concepts)}
