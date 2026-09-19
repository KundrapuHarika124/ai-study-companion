"""Activity events: the single source for activity feeds, analytics, admin and workflows."""
from __future__ import annotations
from pymongo.errors import DuplicateKeyError
from app.core.utils import new_id, now


async def record(db, *, user_id: str, type: str, project_id: str | None = None, space_id: str | None = None,
                 payload: dict | None = None, dedupe_key: str | None = None) -> dict | None:
    doc = {"_id": new_id(), "user_id": user_id, "type": type, "project_id": project_id, "space_id": space_id,
           "payload": payload or {}, "created_at": now()}
    if dedupe_key:
        doc["dedupe_key"] = dedupe_key
    try:
        await db.activity_events.insert_one(doc)
    except DuplicateKeyError:
        return None
    if project_id:
        await db.projects.update_one({"_id": project_id}, {"$set": {"last_activity_at": doc["created_at"], "last_activity_type": type}})
    return doc
