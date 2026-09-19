"""Analytics from real stored events, answers, mastery and AI runs. Aggregation queries, no fabricated numbers."""
from __future__ import annotations
from datetime import timedelta
from app.core.utils import now


async def activity_by_day(db, match: dict, days: int = 30) -> list[dict]:
    since = now() - timedelta(days=days)
    counts: dict[str, int] = {}
    async for e in db.activity_events.find({**match, "created_at": {"$gte": since}}, {"created_at": 1}):
        day = e["created_at"].strftime("%Y-%m-%d")
        counts[day] = counts.get(day, 0) + 1
    return [{"day": d, "count": c} for d, c in sorted(counts.items())]


async def events_by_type(db, match: dict, days: int = 30) -> list[dict]:
    since = now() - timedelta(days=days)
    pipeline = [{"$match": {**match, "created_at": {"$gte": since}}}, {"$group": {"_id": "$type", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return [{"type": r["_id"], "count": r["count"]} async for r in db.activity_events.aggregate(pipeline)]


async def quiz_stats(db, match: dict) -> dict:
    pipeline = [{"$match": match}, {"$group": {"_id": "$difficulty", "avg": {"$avg": "$score"}, "n": {"$sum": 1}}}]
    by_diff = [{"difficulty": r["_id"], "avg": round(r["avg"], 3), "n": r["n"]} async for r in db.quiz_answers.aggregate(pipeline)]
    total = await db.quiz_answers.count_documents(match)
    avg = None
    if total:
        agg = [r async for r in db.quiz_answers.aggregate([{"$match": match}, {"$group": {"_id": None, "avg": {"$avg": "$score"}}}])]
        avg = round(agg[0]["avg"], 3) if agg else None
    sessions = await db.quiz_sessions.count_documents({**match, "status": "completed"})
    return {"answers": total, "avg_score": avg, "sessions_completed": sessions, "by_difficulty": by_diff}


async def ai_stats(db, match: dict, days: int = 30) -> dict:
    since = now() - timedelta(days=days)
    pipeline = [{"$match": {**match, "created_at": {"$gte": since}}},
                {"$group": {"_id": "$feature", "runs": {"$sum": 1}, "avg_latency": {"$avg": "$latency_ms"}, "cost": {"$sum": "$estimated_cost_usd"},
                            "failures": {"$sum": {"$cond": ["$success", 0, 1]}}, "in_tokens": {"$sum": "$input_tokens"}, "out_tokens": {"$sum": "$output_tokens"}}},
                {"$sort": {"runs": -1}}]
    rows = [{"feature": r["_id"], "runs": r["runs"], "avg_latency_ms": int(r["avg_latency"] or 0), "cost_usd": round(r["cost"] or 0, 5),
             "failures": r["failures"], "input_tokens": r["in_tokens"], "output_tokens": r["out_tokens"]} async for r in db.ai_runs.aggregate(pipeline)]
    return {"by_feature": rows, "total_runs": sum(r["runs"] for r in rows), "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 5),
            "failures": sum(r["failures"] for r in rows)}


async def mastery_overview(db, match: dict) -> dict:
    rows = await db.mastery.find(match).to_list(500)
    if not rows:
        return {"concepts": 0, "avg": None, "attention": 0, "strong": 0}
    return {"concepts": len(rows), "avg": round(sum(r["mastery"] for r in rows) / len(rows), 3),
            "attention": sum(1 for r in rows if r["mastery"] < 0.6), "strong": sum(1 for r in rows if r["mastery"] >= 0.75)}


async def project_analytics(db, project_id: str) -> dict:
    m = {"project_id": project_id}
    return {"activity_by_day": await activity_by_day(db, m), "events_by_type": await events_by_type(db, m),
            "quiz": await quiz_stats(db, m), "ai": await ai_stats(db, m), "mastery": await mastery_overview(db, m)}


async def global_analytics(db, user_id: str) -> dict:
    m = {"user_id": user_id}
    spaces = await db.spaces.count_documents(m)
    projects = await db.projects.count_documents(m)
    materials = await db.materials.count_documents({**m, "status": "ready"})
    per_project = []
    async for p in db.projects.find(m).sort("last_activity_at", -1).limit(20):
        pm = {"project_id": p["_id"]}
        per_project.append({"project_id": p["_id"], "name": p["name"], "mastery": await mastery_overview(db, pm), "quiz": await quiz_stats(db, pm)})
    return {"spaces": spaces, "projects": projects, "materials_ready": materials, "activity_by_day": await activity_by_day(db, m),
            "events_by_type": await events_by_type(db, m), "quiz": await quiz_stats(db, m), "ai": await ai_stats(db, m),
            "mastery": await mastery_overview(db, m), "per_project": per_project}
