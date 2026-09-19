from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from app.core.config import settings
from app.core.errors import NotFound, BadRequest
from app.core.security import get_current_user
from app.core.utils import public, public_list
from app.db.mongo import get_db
from app.services import documents, ownership, vectorstore

router = APIRouter(tags=["materials"])


@router.get("/projects/{project_id}/materials")
async def list_materials(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return public_list(await db.materials.find({"project_id": project_id}).sort("created_at", -1).to_list(100))


@router.post("/projects/{project_id}/materials", status_code=202)
async def upload_material(project_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    db = get_db()
    project = await ownership.get_project(db, user["id"], project_id)
    data = await file.read()
    if not data:
        raise BadRequest("Empty file")
    doc = await documents.create_material(db, user=user, project=project, filename=file.filename or "upload.pdf", data=data)
    return public(doc)


@router.get("/materials/{material_id}")
async def get_material(material_id: str, user=Depends(get_current_user)):
    db = get_db()
    m = await ownership.get_material(db, user["id"], material_id)
    job = await db.background_jobs.find_one({"idempotency_key": f"process_material:{material_id}"})
    chunks = await db.material_chunks.find({"material_id": material_id}).sort("index", 1).limit(500).to_list(500)
    visuals = await db.visual_assets.find({"material_id": material_id}).sort("page", 1).to_list(100)
    return {"material": public(m), "job": public(job),
            "chunks": [{"chunk_id": c["chunk_id"], "page": c["page"], "heading": c["heading"], "text": c["text"], "concepts": c["concepts"]} for c in chunks],
            "visuals": [{"id": v["_id"], "page": v["page"], "caption": v["caption"], "url": f"/api/materials/{material_id}/visuals/{v['_id']}"} for v in visuals]}


@router.post("/materials/{material_id}/retry")
async def retry(material_id: str, user=Depends(get_current_user)):
    db = get_db()
    m = await ownership.get_material(db, user["id"], material_id)
    if m["status"] not in ("failed", "ready"):
        raise BadRequest("Material is already queued or processing")
    job = await documents.retry_material(db, m)
    return {"material": public(await db.materials.find_one({"_id": material_id})), "job": public(job)}


@router.delete("/materials/{material_id}", status_code=204)
async def delete_material(material_id: str, user=Depends(get_current_user)):
    db = get_db()
    m = await ownership.get_material(db, user["id"], material_id)
    try:
        vectorstore.delete_material(material_id)
    except Exception:  # noqa: BLE001
        pass
    await db.material_chunks.delete_many({"material_id": material_id})
    await db.visual_assets.delete_many({"material_id": material_id})
    await db.materials.delete_one({"_id": material_id})
    p = documents.storage_path(material_id)
    if p.exists():
        p.unlink()
    for c in await db.concepts.find({"material_ids": material_id}).to_list(100):
        remaining = [x for x in c.get("material_ids", []) if x != material_id]
        if remaining:
            await db.concepts.update_one({"_id": c["_id"]}, {"$set": {"material_ids": remaining}})
        else:
            await db.concepts.delete_one({"_id": c["_id"]})
    _ = m


@router.get("/materials/{material_id}/file")
async def download(material_id: str, user=Depends(get_current_user)):
    db = get_db()
    m = await ownership.get_material(db, user["id"], material_id)
    p = documents.storage_path(material_id)
    if not p.exists():
        raise NotFound("File")
    return FileResponse(p, media_type="application/pdf", filename=m["filename"])


@router.get("/materials/{material_id}/visuals/{asset_id}")
async def visual(material_id: str, asset_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_material(db, user["id"], material_id)
    a = await db.visual_assets.find_one({"_id": asset_id, "material_id": material_id})
    if not a:
        raise NotFound("Visual")
    p = Path(settings.STORAGE_DIR) / "visuals" / a["file"]
    if not p.exists():
        raise NotFound("Visual file")
    return FileResponse(p)
