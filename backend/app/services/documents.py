"""PDF material pipeline: validate → store → (job) extract/OCR → chunk → concepts → embed → index → READY."""
from __future__ import annotations
import asyncio
import hashlib
import logging
import os
import re
from pathlib import Path
from pydantic import BaseModel
from app.core.config import settings
from app.core.errors import BadRequest
from app.core.utils import new_id, now, truncate
from app.services import embeddings, vectorstore, events
from app.services.jobs import handler, enqueue
from app.services.llm import llm, DATA_GUARD

log = logging.getLogger("documents")
MAX_PDF_BYTES = 40 * 1024 * 1024
CHUNK_TARGET = 900
CHUNK_OVERLAP = 150


def storage_path(material_id: str) -> Path:
    base = Path(settings.STORAGE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{material_id}.pdf"


async def create_material(db, *, user: dict, project: dict, filename: str, data: bytes) -> dict:
    if not filename.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
        raise BadRequest("Only PDF files are supported")
    if len(data) > MAX_PDF_BYTES:
        raise BadRequest("PDF exceeds the 40 MB limit")
    digest = hashlib.sha256(data).hexdigest()
    dup = await db.materials.find_one({"project_id": project["_id"], "sha256": digest, "status": {"$ne": "failed"}})
    if dup:
        return dup  # same file uploaded twice into the same project: reuse, do not reprocess
    mid = new_id()
    storage_path(mid).write_bytes(data)
    safe_name = re.sub(r"[^\w .()-]", "_", filename)[:140]
    doc = {"_id": mid, "user_id": user["id"], "project_id": project["_id"], "space_id": project["space_id"],
           "filename": safe_name, "title": Path(safe_name).stem, "size_bytes": len(data), "sha256": digest,
           "status": "queued", "error": None, "page_count": None, "chunk_count": 0, "visual_count": 0, "ocr_pages": 0,
           "concepts": [], "created_at": now(), "updated_at": now(), "processed_at": None}
    await db.materials.insert_one(doc)
    await events.record(db, user_id=user["id"], type="material_uploaded", project_id=project["_id"], space_id=project["space_id"],
                        payload={"material_id": mid, "filename": safe_name})
    await enqueue(db, type="process_material", payload={"material_id": mid}, user_id=user["id"], project_id=project["_id"],
                  idempotency_key=f"process_material:{mid}")
    return doc


async def retry_material(db, material: dict) -> dict:
    await db.materials.update_one({"_id": material["_id"]}, {"$set": {"status": "queued", "error": None, "updated_at": now()}})
    return await enqueue(db, type="process_material", payload={"material_id": material["_id"]}, user_id=material["user_id"],
                         project_id=material["project_id"], idempotency_key=f"process_material:{material['_id']}")


# ---------------- extraction ----------------

def _ocr_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False


def extract_pdf(path: Path) -> dict:
    """Returns {pages:[{page, text, ocr, heading}], images:[{page, bytes, ext, caption}]}."""
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    pages, images = [], []
    ocr_ok = None
    for pno, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        used_ocr = False
        if len(text.strip()) < 40:
            if ocr_ok is None:
                ocr_ok = _ocr_available()
            if ocr_ok:
                try:
                    import pytesseract
                    from PIL import Image
                    import io
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img) or ""
                    used_ocr = True
                except Exception as e:  # noqa: BLE001
                    log.warning("OCR failed on page %s: %s", pno, e)
        # tables: PyMuPDF find_tables (best effort)
        try:
            tabs = page.find_tables()
            for t in tabs.tables[:5]:
                rows = t.extract()
                if rows:
                    text += "\n\n[TABLE]\n" + "\n".join(" | ".join(str(c or "").strip() for c in r) for r in rows[:40]) + "\n[/TABLE]\n"
        except Exception:  # noqa: BLE001
            pass
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        heading = next((l for l in lines[:5] if 3 < len(l) < 90), "")
        pages.append({"page": pno, "text": text, "ocr": used_ocr, "heading": heading})
        try:
            for img_info in page.get_images(full=True)[:6]:
                xref = img_info[0]
                base = doc.extract_image(xref)
                if not base or base.get("width", 0) < 120 or base.get("height", 0) < 120:
                    continue
                caption = heading or truncate(" ".join(lines[:3]), 160)
                images.append({"page": pno, "bytes": base["image"], "ext": base.get("ext", "png"), "caption": caption,
                               "width": base.get("width"), "height": base.get("height")})
        except Exception as e:  # noqa: BLE001
            log.debug("image extraction skipped p%s: %s", pno, e)
    return {"pages": pages, "images": images, "page_count": len(doc)}


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Paragraph-aware chunking with overlap; every chunk keeps page + heading."""
    chunks = []
    for p in pages:
        paras = [x.strip() for x in re.split(r"\n\s*\n", p["text"]) if x.strip()]
        buf = ""
        for para in paras:
            if len(buf) + len(para) + 1 > CHUNK_TARGET and buf:
                chunks.append({"page": p["page"], "heading": p["heading"], "text": buf.strip()})
                buf = buf[-CHUNK_OVERLAP:] + "\n" + para
            else:
                buf = (buf + "\n" + para) if buf else para
        if len(buf.strip()) > 40:
            chunks.append({"page": p["page"], "heading": p["heading"], "text": buf.strip()})
    # drop tiny fragments
    return [c for c in chunks if len(c["text"]) >= 60]


class _ConceptList(BaseModel):
    concepts: list[dict]


async def extract_concepts(db, material: dict, pages: list[dict]) -> list[dict]:
    """LLM concept extraction over a sample of the document. Falls back to headings if AI is unavailable."""
    sample_parts, budget = [], 9000
    for p in pages:
        if not p["text"].strip():
            continue
        piece = f"[p{p['page']}] {truncate(p['text'].strip(), 700)}"
        if budget - len(piece) < 0:
            break
        sample_parts.append(piece); budget -= len(piece)
    headings = [p["heading"] for p in pages if p["heading"]]
    if not llm.available or not sample_parts:
        uniq = []
        for h in headings:
            if h not in uniq: uniq.append(h)
        return [{"name": h, "description": ""} for h in uniq[:12]]
    prompt = (f"{DATA_GUARD}\n\nExtract the 6-14 most important learnable concepts from this study material. "
              "Concepts should be specific topics a learner could be quizzed on (e.g. 'TCP three-way handshake'), not chapter titles. "
              "Return JSON: {\"concepts\":[{\"name\":\"...\",\"description\":\"one sentence\",\"keywords\":[\"...\"]}]}\n\n"
              f"<data>\nTitle: {material['title']}\nHeadings: {headings[:40]}\n\n" + "\n\n".join(sample_parts) + "\n</data>")
    try:
        out = await llm.generate_json(prompt, _ConceptList, feature="concept_extraction", user_id=material["user_id"],
                                      project_id=material["project_id"], db=db, temperature=0.2)
        cleaned = []
        for c in out.concepts[:14]:
            name = str(c.get("name", "")).strip()[:80]
            if name:
                cleaned.append({"name": name, "description": str(c.get("description", ""))[:300],
                                "keywords": [str(k).lower()[:40] for k in c.get("keywords", [])][:8]})
        return cleaned
    except Exception as e:  # noqa: BLE001
        log.warning("concept extraction failed, using headings: %s", e)
        return [{"name": h, "description": ""} for h in headings[:12]]


def tag_chunk_concepts(chunk_text: str, concepts: list[dict]) -> list[str]:
    t = chunk_text.lower()
    tags = []
    for c in concepts:
        terms = [c["name"].lower()] + c.get("keywords", [])
        if any(term and term in t for term in terms):
            tags.append(c["name"])
    return tags[:5]


@handler("process_material")
async def process_material_job(db, job: dict) -> None:
    mid = job["payload"]["material_id"]
    material = await db.materials.find_one({"_id": mid})
    if not material:
        return
    if material["status"] == "ready" and material.get("chunk_count"):
        return  # idempotent: already processed
    await db.materials.update_one({"_id": mid}, {"$set": {"status": "processing", "error": None, "updated_at": now()}})
    await events.record(db, user_id=material["user_id"], type="material_processing_started", project_id=material["project_id"],
                        space_id=material["space_id"], payload={"material_id": mid}, dedupe_key=f"mps:{mid}:{job['attempts']}")
    path = storage_path(mid)
    if not path.exists():
        raise FileNotFoundError("stored PDF missing")
    extracted = await asyncio.to_thread(extract_pdf, path)
    pages = extracted["pages"]
    total_text = sum(len(p["text"].strip()) for p in pages)
    if total_text < 80:
        msg = "No extractable text found. " + ("The PDF appears to be scanned but OCR (Tesseract) is not installed." if not _ocr_available() else "OCR produced no readable text.")
        raise ValueError(msg)
    concepts = await extract_concepts(db, material, pages)
    chunks = chunk_pages(pages)
    # replace any previous chunks/vectors for this material (safe re-processing)
    await db.material_chunks.delete_many({"material_id": mid})
    await db.visual_assets.delete_many({"material_id": mid})
    try:
        vectorstore.delete_material(mid)
    except Exception:  # noqa: BLE001
        pass
    chunk_docs, texts = [], []
    for i, c in enumerate(chunks):
        cid = f"{mid}:{c['page']}:{i}"
        chunk_docs.append({"_id": cid, "chunk_id": cid, "material_id": mid, "project_id": material["project_id"],
                           "user_id": material["user_id"], "page": c["page"], "heading": c["heading"], "text": c["text"],
                           "concepts": tag_chunk_concepts(c["text"], concepts), "type": "text", "index": i})
        texts.append(f"{c['heading']}\n{c['text']}" if c["heading"] else c["text"])
    # visual assets (images with captions) are indexed too so the Tutor can prefer the learner's own diagrams
    vis_docs = []
    vis_dir = Path(settings.STORAGE_DIR) / "visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    for j, im in enumerate(extracted["images"][:60]):
        vid = f"{mid}:img:{im['page']}:{j}"
        fname = f"{vid.replace(':', '_')}.{im['ext']}"
        (vis_dir / fname).write_bytes(im["bytes"])
        vis_docs.append({"_id": vid, "material_id": mid, "project_id": material["project_id"], "user_id": material["user_id"],
                         "page": im["page"], "caption": im["caption"], "file": fname, "width": im["width"], "height": im["height"],
                         "concepts": tag_chunk_concepts(im["caption"], concepts), "created_at": now()})
    vectors = await embeddings.embed(texts + [f"Figure on page {v['page']}: {v['caption']}" for v in vis_docs])
    vectorstore.ensure_collection(len(vectors[0]) if vectors else embeddings.dimension())
    points = []
    for d, v in zip(chunk_docs, vectors[: len(chunk_docs)]):
        points.append({"id": _point_id(d["chunk_id"]), "vector": v, "payload": {
            "chunk_id": d["chunk_id"], "user_id": d["user_id"], "project_id": d["project_id"], "space_id": material["space_id"],
            "material_id": mid, "page": d["page"], "type": "text", "concepts": d["concepts"], "heading": d["heading"],
            "text": truncate(d["text"], 1200), "title": material["title"]}})
    for d, v in zip(vis_docs, vectors[len(chunk_docs):]):
        points.append({"id": _point_id(d["_id"]), "vector": v, "payload": {
            "chunk_id": d["_id"], "user_id": d["user_id"], "project_id": d["project_id"], "space_id": material["space_id"],
            "material_id": mid, "page": d["page"], "type": "visual", "concepts": d["concepts"], "text": d["caption"], "title": material["title"]}})
    vectorstore.upsert(points)
    if chunk_docs:
        await db.material_chunks.insert_many(chunk_docs)
    if vis_docs:
        await db.visual_assets.insert_many(vis_docs)
    for c in concepts:
        await db.concepts.update_one({"project_id": material["project_id"], "name": c["name"]},
                                     {"$set": {"description": c.get("description", ""), "keywords": c.get("keywords", []), "updated_at": now()},
                                      "$setOnInsert": {"_id": new_id(), "user_id": material["user_id"], "created_at": now()},
                                      "$addToSet": {"material_ids": mid}}, upsert=True)
    await db.materials.update_one({"_id": mid}, {"$set": {
        "status": "ready", "page_count": extracted["page_count"], "chunk_count": len(chunk_docs), "visual_count": len(vis_docs),
        "ocr_pages": sum(1 for p in pages if p["ocr"]), "concepts": [c["name"] for c in concepts], "processed_at": now(), "updated_at": now()}})
    await events.record(db, user_id=material["user_id"], type="material_processed", project_id=material["project_id"],
                        space_id=material["space_id"], payload={"material_id": mid, "chunks": len(chunk_docs), "pages": extracted["page_count"],
                                                                "concepts": len(concepts)}, dedupe_key=f"mpd:{mid}")


async def _on_final_failure(db, job: dict, err: str):
    mid = job["payload"]["material_id"]
    await db.materials.update_one({"_id": mid}, {"$set": {"status": "failed", "error": err, "updated_at": now()}})
    m = await db.materials.find_one({"_id": mid})
    if m:
        await events.record(db, user_id=m["user_id"], type="material_failed", project_id=m["project_id"], space_id=m["space_id"],
                            payload={"material_id": mid, "error": err})


process_material_job.on_final_failure = _on_final_failure


def _point_id(s: str) -> str:
    """Qdrant point ids must be UUIDs or ints: derive a stable UUID from the chunk id."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, s))
