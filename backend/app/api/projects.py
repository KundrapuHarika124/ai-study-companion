from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.core.utils import new_id, now, public, public_list
from app.db.mongo import get_db
from app.schemas import ProjectCreate, ProjectUpdate
from app.services import events, ownership, analytics, recommendations, vectorstore

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(user=Depends(get_current_user)):
    db = get_db()
    return public_list(await db.projects.find({"user_id": user["id"]}).sort("last_activity_at", -1).to_list(200))


@router.post("", status_code=201)
async def create_project(body: ProjectCreate, user=Depends(get_current_user)):
    db = get_db()
    space = await ownership.get_space(db, user["id"], body.space_id)
    doc = {"_id": new_id(), "user_id": user["id"], "space_id": space["_id"], "name": body.name, "description": body.description,
           "learning_goal": body.learning_goal, "created_at": now(), "updated_at": now(), "last_activity_at": now(), "last_activity_type": "project_created"}
    await db.projects.insert_one(doc)
    await db.spaces.update_one({"_id": space["_id"]}, {"$set": {"updated_at": now()}})
    await events.record(db, user_id=user["id"], type="project_created", project_id=doc["_id"], space_id=space["_id"], payload={"name": doc["name"]})
    return public(doc)


@router.get("/{project_id}")
async def get_project(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    p = await ownership.get_project(db, user["id"], project_id)
    space = await db.spaces.find_one({"_id": p["space_id"]})
    materials = await db.materials.find({"project_id": project_id}).sort("created_at", -1).to_list(50)
    concepts = await db.concepts.find({"project_id": project_id}).to_list(50)
    mastery = await db.mastery.find({"project_id": project_id}).sort("mastery", 1).to_list(50)
    mmap = {m["concept"]: m for m in mastery}
    concept_out = [{"name": c["name"], "description": c.get("description", ""), "mastery": mmap[c["name"]]["mastery"] if c["name"] in mmap else None,
                    "evidence_count": mmap[c["name"]]["evidence_count"] if c["name"] in mmap else 0} for c in concepts]
    concept_out.sort(key=lambda c: (c["mastery"] is None, c["mastery"] if c["mastery"] is not None else 0))
    activity = await db.activity_events.find({"project_id": project_id}).sort("created_at", -1).limit(12).to_list(12)
    rec = await recommendations.current(db, project_id)
    quiz = await analytics.quiz_stats(db, {"project_id": project_id})
    last_conv = await db.conversations.find_one({"project_id": project_id}, sort=[("updated_at", -1)])
    return {"project": public(p), "space": public(space), "materials": public_list(materials), "concepts": concept_out,
            "mastery_overview": await analytics.mastery_overview(db, {"project_id": project_id}), "quiz": quiz,
            "activity": public_list(activity), "recommendation": public(rec), "last_conversation": public(last_conv)}


@router.patch("/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    upd["updated_at"] = now()
    await db.projects.update_one({"_id": project_id}, {"$set": upd})
    return public(await db.projects.find_one({"_id": project_id}))


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    for m in await db.materials.find({"project_id": project_id}).to_list(500):
        try:
            vectorstore.delete_material(m["_id"])
        except Exception:  # noqa: BLE001
            pass
    for col in ("materials", "material_chunks", "visual_assets", "concepts", "conversations", "messages", "quiz_sessions", "quiz_questions",
                "quiz_answers", "mastery", "mastery_history", "recommendations", "learner_context", "activity_events"):
        await db[col].delete_many({"project_id": project_id})
    await db.projects.delete_one({"_id": project_id})


@router.post("/{project_id}/recommendations/refresh")
async def refresh_recommendation(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    p = await ownership.get_project(db, user["id"], project_id)
    return public(await recommendations.generate(db, user=user, project=p, trigger="manual_refresh"))
