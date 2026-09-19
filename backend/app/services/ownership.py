"""Every project-scoped operation goes through here so ownership is checked in one place."""
from app.core.errors import NotFound


async def get_space(db, user_id: str, space_id: str) -> dict:
    doc = await db.spaces.find_one({"_id": space_id, "user_id": user_id})
    if not doc:
        raise NotFound("Space")
    return doc


async def get_project(db, user_id: str, project_id: str) -> dict:
    doc = await db.projects.find_one({"_id": project_id, "user_id": user_id})
    if not doc:
        raise NotFound("Project")
    return doc


async def get_material(db, user_id: str, material_id: str) -> dict:
    doc = await db.materials.find_one({"_id": material_id, "user_id": user_id})
    if not doc:
        raise NotFound("Material")
    return doc
