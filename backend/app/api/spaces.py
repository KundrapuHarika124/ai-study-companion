from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.core.utils import new_id, now, public, public_list
from app.db.mongo import get_db
from app.schemas import SpaceCreate, SpaceUpdate
from app.services import events, ownership, analytics

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.get("")
async def list_spaces(user=Depends(get_current_user)):
    db = get_db()
    spaces = await db.spaces.find({"user_id": user["id"]}).sort("updated_at", -1).to_list(200)
    out = []
    for s in spaces:
        s["project_count"] = await db.projects.count_documents({"space_id": s["_id"]})
        out.append(public(s))
    return out


@router.post("", status_code=201)
async def create_space(body: SpaceCreate, user=Depends(get_current_user)):
    db = get_db()
    doc = {"_id": new_id(), "user_id": user["id"], **body.model_dump(), "created_at": now(), "updated_at": now()}
    await db.spaces.insert_one(doc)
    await events.record(db, user_id=user["id"], type="space_created", space_id=doc["_id"], payload={"name": doc["name"]})
    return public(doc)


@router.get("/{space_id}")
async def get_space(space_id: str, user=Depends(get_current_user)):
    db = get_db()
    space = await ownership.get_space(db, user["id"], space_id)
    projects = await db.projects.find({"space_id": space_id, "user_id": user["id"]}).sort("last_activity_at", -1).to_list(100)
    proj_out = []
    attention = []
    for p in projects:
        pm = await analytics.mastery_overview(db, {"project_id": p["_id"]})
        rec = await db.recommendations.find_one({"project_id": p["_id"], "status": "active"})
        mats = await db.materials.count_documents({"project_id": p["_id"], "status": "ready"})
        weak = await db.mastery.find({"project_id": p["_id"], "mastery": {"$lt": 0.6}}).sort("mastery", 1).limit(3).to_list(3)
        attention += [{"project_id": p["_id"], "project": p["name"], "concept": w["concept"], "mastery": w["mastery"]} for w in weak]
        proj_out.append({**public(p), "mastery": pm, "materials_ready": mats, "recommendation": public(rec)})
    activity = await db.activity_events.find({"space_id": space_id, "user_id": user["id"]}).sort("created_at", -1).limit(15).to_list(15)
    return {"space": public(space), "projects": proj_out, "activity": public_list(activity),
            "attention": sorted(attention, key=lambda a: a["mastery"])[:6], "activity_by_day": await analytics.activity_by_day(db, {"space_id": space_id, "user_id": user["id"]})}


@router.patch("/{space_id}")
async def update_space(space_id: str, body: SpaceUpdate, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_space(db, user["id"], space_id)
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    upd["updated_at"] = now()
    await db.spaces.update_one({"_id": space_id}, {"$set": upd})
    return public(await db.spaces.find_one({"_id": space_id}))


@router.delete("/{space_id}", status_code=204)
async def delete_space(space_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_space(db, user["id"], space_id)
    n = await db.projects.count_documents({"space_id": space_id})
    if n:
        from app.core.errors import Conflict
        raise Conflict("Delete or move the projects in this space first")
    await db.spaces.delete_one({"_id": space_id, "user_id": user["id"]})
