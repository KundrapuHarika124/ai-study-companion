"""Persistent, relevance-filtered learner context per project."""
from __future__ import annotations
from app.core.utils import new_id, now

EMPTY = {"strengths": [], "weaknesses": [], "repeated_mistakes": [], "notes": [], "recent_topics": [], "preferences": {}}


async def get(db, project_id: str) -> dict:
    doc = await db.learner_context.find_one({"project_id": project_id})
    if not doc:
        return {**EMPTY, "project_id": project_id}
    return doc


async def update(db, *, user_id: str, project_id: str, **fields) -> None:
    sets = {k: v for k, v in fields.items() if v is not None}
    sets["updated_at"] = now()
    await db.learner_context.update_one({"project_id": project_id}, {"$set": sets, "$setOnInsert": {"_id": new_id(), "user_id": user_id, "created_at": now()}}, upsert=True)


async def note_topic(db, *, user_id: str, project_id: str, topic: str) -> None:
    if not topic:
        return
    ctx = await get(db, project_id)
    topics = [t for t in ctx.get("recent_topics", []) if t != topic][-9:] + [topic]
    await update(db, user_id=user_id, project_id=project_id, recent_topics=topics)


async def compose(db, *, project: dict, task: str, concept_hint: str = "") -> str:
    """Build a short, task-relevant context block. Never the whole history."""
    ctx = await get(db, project["_id"])
    mastery = await db.mastery.find({"project_id": project["_id"]}).sort("mastery", 1).to_list(50)
    weak = [f"{m['concept']} ({int(m['mastery']*100)}%)" for m in mastery if m["mastery"] < 0.6][:5]
    strong = [f"{m['concept']} ({int(m['mastery']*100)}%)" for m in mastery if m["mastery"] >= 0.75][:4]
    lines = [f"Learning goal: {project.get('learning_goal') or 'not specified'}"]
    if task in ("tutor", "quiz", "recommend"):
        if weak: lines.append("Concepts needing attention: " + ", ".join(weak))
        if strong and task != "quiz": lines.append("Strong concepts: " + ", ".join(strong))
    if task in ("tutor", "recommend") and ctx.get("repeated_mistakes"):
        lines.append("Repeated mistakes: " + "; ".join(str(m.get("summary", m)) if isinstance(m, dict) else str(m) for m in ctx["repeated_mistakes"][-3:]))
    if task == "tutor" and ctx.get("recent_topics"):
        lines.append("Recently discussed: " + ", ".join(ctx["recent_topics"][-4:]))
    if concept_hint:
        recent = await db.quiz_answers.find({"project_id": project["_id"], "concept": concept_hint}).sort("created_at", -1).limit(3).to_list(3)
        if recent:
            lines.append(f"Recent quiz results on '{concept_hint}': " + ", ".join("correct" if a["score"] >= 0.7 else "incorrect" for a in recent))
    return "\n".join(lines)
