"""Mastery, growth, recommendations, analytics, activity, home."""
from fastapi import APIRouter, Depends, Query
from app.core.security import get_current_user
from app.core.utils import public, public_list
from app.db.mongo import get_db
from app.services import ownership, mastery, growth, recommendations, analytics

router = APIRouter(tags=["learning"])


@router.get("/projects/{project_id}/mastery")
async def project_mastery(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    concepts = [c["name"] async for c in db.concepts.find({"project_id": project_id})]
    snap = await mastery.snapshot(db, project_id)
    assessed = {s["concept"] for s in snap}
    return {"assessed": snap, "unassessed": [c for c in concepts if c not in assessed]}


@router.get("/projects/{project_id}/growth")
async def project_growth(project_id: str, days: int = Query(30, ge=1, le=365), user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return await growth.analyze(db, project_id, days)


@router.get("/projects/{project_id}/recommendations")
async def project_recs(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return {"current": public(await recommendations.current(db, project_id)),
            "history": public_list(await db.recommendations.find({"project_id": project_id}).sort("created_at", -1).limit(10).to_list(10))}


@router.get("/projects/{project_id}/analytics")
async def project_analytics(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return await analytics.project_analytics(db, project_id)


@router.get("/projects/{project_id}/activity")
async def project_activity(project_id: str, limit: int = Query(30, le=200), before: str | None = None, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    q = {"project_id": project_id}
    if before:
        from datetime import datetime
        q["created_at"] = {"$lt": datetime.fromisoformat(before)}
    return public_list(await db.activity_events.find(q).sort("created_at", -1).limit(limit).to_list(limit))


@router.get("/analytics/global")
async def global_analytics(user=Depends(get_current_user)):
    return await analytics.global_analytics(get_db(), user["id"])


@router.get("/activity")
async def my_activity(limit: int = Query(40, le=200), type: str | None = None, user=Depends(get_current_user)):
    db = get_db()
    q = {"user_id": user["id"]}
    if type:
        q["type"] = type
    return public_list(await db.activity_events.find(q).sort("created_at", -1).limit(limit).to_list(limit))


@router.get("/home")
async def home(user=Depends(get_current_user)):
    """Where was I? How am I doing? What should I do next?"""
    db = get_db()
    projects = await db.projects.find({"user_id": user["id"]}).sort("last_activity_at", -1).limit(6).to_list(6)
    recent = []
    for p in projects:
        space = await db.spaces.find_one({"_id": p["space_id"]})
        recent.append({**public(p), "space_name": space["name"] if space else "", "space_color": space.get("color") if space else None,
                       "mastery": await analytics.mastery_overview(db, {"project_id": p["_id"]})})
    continue_learning = recent[0] if recent else None
    last_conv = None
    if continue_learning:
        last_conv = public(await db.conversations.find_one({"project_id": continue_learning["id"]}, sort=[("updated_at", -1)]))
    weak = await db.mastery.find({"user_id": user["id"], "mastery": {"$lt": 0.6}}).sort("mastery", 1).limit(6).to_list(6)
    pnames = {p["_id"]: p["name"] for p in projects}
    for w in weak:
        if w["project_id"] not in pnames:
            pr = await db.projects.find_one({"_id": w["project_id"]})
            pnames[w["project_id"]] = pr["name"] if pr else ""
    rec = None
    if continue_learning:
        rec = public(await recommendations.current(db, continue_learning["id"]))
    return {"user": user, "continue_learning": continue_learning, "last_conversation": last_conv, "recent_projects": recent,
            "overall": await analytics.mastery_overview(db, {"user_id": user["id"]}), "quiz": await analytics.quiz_stats(db, {"user_id": user["id"]}),
            "attention": [{"concept": w["concept"], "mastery": w["mastery"], "project_id": w["project_id"], "project": pnames.get(w["project_id"], "")} for w in weak],
            "recommendation": rec, "space_count": await db.spaces.count_documents({"user_id": user["id"]})}
