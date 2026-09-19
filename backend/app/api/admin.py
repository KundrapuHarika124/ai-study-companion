"""Admin: platform-level visibility. Every route requires is_admin (enforced on the backend, not just hidden in the UI)."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from app.core.config import settings
from app.core.security import require_admin
from app.core.utils import now, public, public_list
from app.db.mongo import get_db
from app.services import analytics, vectorstore
from app.services.llm import llm

router = APIRouter(prefix="/admin", tags=["admin"])


def _since(days: int) -> datetime:
    return now() - timedelta(days=days)


@router.get("/overview")
async def overview(days: int = Query(30, ge=1, le=365), admin=Depends(require_admin)):
    db = get_db()
    since = _since(days)
    active_users = len(await db.activity_events.distinct("user_id", {"created_at": {"$gte": since}}))
    return {"users": await db.users.count_documents({}), "active_users": active_users, "spaces": await db.spaces.count_documents({}),
            "projects": await db.projects.count_documents({}), "materials": await db.materials.count_documents({}),
            "materials_failed": await db.materials.count_documents({"status": "failed"}),
            "quiz_answers": await db.quiz_answers.count_documents({"created_at": {"$gte": since}}),
            "tutor_messages": await db.messages.count_documents({"role": "assistant", "created_at": {"$gte": since}}),
            "activity_by_day": await analytics.activity_by_day(db, {}, days), "events_by_type": await analytics.events_by_type(db, {}, days),
            "ai": await analytics.ai_stats(db, {}, days), "mastery": await analytics.mastery_overview(db, {}),
            "jobs": {s: await db.background_jobs.count_documents({"status": s}) for s in ("queued", "processing", "retrying", "completed", "failed")}}


@router.get("/users")
async def users(q: str | None = None, limit: int = Query(50, le=200), admin=Depends(require_admin)):
    db = get_db()
    match = {"email": {"$regex": q, "$options": "i"}} if q else {}
    out = []
    for u in await db.users.find(match).sort("last_seen_at", -1).limit(limit).to_list(limit):
        out.append({**public(u), "projects": await db.projects.count_documents({"user_id": u["_id"]}),
                    "events": await db.activity_events.count_documents({"user_id": u["_id"]})})
    return out


@router.get("/users/{user_id}")
async def user_detail(user_id: str, admin=Depends(require_admin)):
    db = get_db()
    u = await db.users.find_one({"_id": user_id})
    projects = await db.projects.find({"user_id": user_id}).sort("last_activity_at", -1).to_list(100)
    pj = []
    for p in projects:
        pj.append({**public(p), "mastery": await analytics.mastery_overview(db, {"project_id": p["_id"]}),
                   "quiz": await analytics.quiz_stats(db, {"project_id": p["_id"]}),
                   "materials": await db.materials.count_documents({"project_id": p["_id"]})})
    return {"user": public(u), "projects": pj, "spaces": public_list(await db.spaces.find({"user_id": user_id}).to_list(50)),
            "activity": public_list(await db.activity_events.find({"user_id": user_id}).sort("created_at", -1).limit(50).to_list(50)),
            "assessments": public_list(await db.quiz_sessions.find({"user_id": user_id}).sort("created_at", -1).limit(20).to_list(20)),
            "ai": await analytics.ai_stats(db, {"user_id": user_id}, 90),
            "recommendations": public_list(await db.recommendations.find({"user_id": user_id}).sort("created_at", -1).limit(10).to_list(10))}


@router.get("/activity")
async def activity(user_id: str | None = None, space_id: str | None = None, project_id: str | None = None, type: str | None = None,
                   days: int = Query(30, ge=1, le=365), limit: int = Query(100, le=500), admin=Depends(require_admin)):
    db = get_db()
    q: dict = {"created_at": {"$gte": _since(days)}}
    for k, v in (("user_id", user_id), ("space_id", space_id), ("project_id", project_id), ("type", type)):
        if v:
            q[k] = v
    return public_list(await db.activity_events.find(q).sort("created_at", -1).limit(limit).to_list(limit))


@router.get("/ai-runs")
async def ai_runs(feature: str | None = None, failed: bool = False, user_id: str | None = None, limit: int = Query(100, le=500), admin=Depends(require_admin)):
    db = get_db()
    q: dict = {}
    if feature: q["feature"] = feature
    if failed: q["success"] = False
    if user_id: q["user_id"] = user_id
    runs = await db.ai_runs.find(q).sort("created_at", -1).limit(limit).to_list(limit)
    slow = await db.ai_runs.find({"success": True}).sort("latency_ms", -1).limit(10).to_list(10)
    return {"runs": public_list(runs), "slowest": public_list(slow), "stats": await analytics.ai_stats(db, {}, 30)}


@router.get("/jobs")
async def jobs(status: str | None = None, limit: int = Query(100, le=500), admin=Depends(require_admin)):
    db = get_db()
    q = {"status": status} if status else {}
    return public_list(await db.background_jobs.find(q).sort("updated_at", -1).limit(limit).to_list(limit))


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, admin=Depends(require_admin)):
    from app.services.jobs import dispatch
    db = get_db()
    await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "queued", "attempts": 0, "error": None, "updated_at": now()}})
    dispatch(job_id)
    return public(await db.background_jobs.find_one({"_id": job_id}))


@router.get("/evaluations")
async def evaluations(limit: int = Query(20, le=100), admin=Depends(require_admin)):
    db = get_db()
    return public_list(await db.ai_evaluations.find({}).sort("created_at", -1).limit(limit).to_list(limit))


@router.get("/health")
async def health(admin=Depends(require_admin)):
    db = get_db()
    mongo_ok = True
    try:
        await db.command("ping")
    except Exception:  # noqa: BLE001
        mongo_ok = False
    redis_ok = None
    if settings.REDIS_URL:
        try:
            import redis
            redis_ok = bool(redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping())
        except Exception:  # noqa: BLE001
            redis_ok = False
    stuck = await db.background_jobs.count_documents({"status": {"$in": ["processing", "retrying"]}, "updated_at": {"$lt": _since(0) - timedelta(minutes=15)}})
    return {"mongo": mongo_ok, "qdrant": vectorstore.healthy(), "redis": redis_ok, "job_backend": settings.job_backend,
            "ai_configured": llm.available, "model": settings.GEMINI_MODEL, "auth_mode": settings.AUTH_MODE, "stuck_jobs": stuck, "env": settings.APP_ENV}
