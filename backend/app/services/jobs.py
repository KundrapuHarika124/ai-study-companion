"""Background job abstraction with idempotency, retries and recovery.

Backends: `celery` (Redis broker, separate worker) or `inline` (runs in the API process via asyncio; the
browser does not need to stay open either way). Job state is always persisted in Mongo so the UI and admin
can show real progress and failures can be retried.
"""
from __future__ import annotations
import asyncio
import logging
import traceback
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
from app.core.utils import new_id, now

log = logging.getLogger("jobs")
MAX_ATTEMPTS = 3
HANDLERS: dict[str, "callable"] = {}


def handler(job_type: str):
    def deco(fn):
        HANDLERS[job_type] = fn
        return fn
    return deco


async def enqueue(db, *, type: str, payload: dict, user_id: str, idempotency_key: str, project_id: str | None = None) -> dict:
    """Create the job if it does not exist (or exists in a terminal state). Returns the job doc."""
    existing = await db.background_jobs.find_one({"idempotency_key": idempotency_key})
    if existing and existing["status"] in ("queued", "processing", "retrying"):
        return existing  # duplicate request: do not create duplicate work
    doc = {"_id": new_id(), "type": type, "payload": payload, "user_id": user_id, "project_id": project_id,
           "idempotency_key": idempotency_key, "status": "queued", "attempts": 0, "max_attempts": MAX_ATTEMPTS,
           "error": None, "created_at": now(), "updated_at": now(), "started_at": None, "finished_at": None}
    if existing:
        await db.background_jobs.replace_one({"_id": existing["_id"]}, {**doc, "_id": existing["_id"]})
        doc["_id"] = existing["_id"]
    else:
        try:
            await db.background_jobs.insert_one(doc)
        except DuplicateKeyError:
            return await db.background_jobs.find_one({"idempotency_key": idempotency_key})
    dispatch(doc["_id"])
    return doc


def dispatch(job_id: str) -> None:
    if settings.job_backend == "celery":
        from app.workers.celery_app import run_job_task
        run_job_task.delay(job_id)
    else:
        loop = asyncio.get_event_loop()
        loop.create_task(run_job(job_id))


async def run_job(job_id: str, db=None) -> None:
    from app.db.mongo import get_db
    db = get_db() if db is None else db
    job = await db.background_jobs.find_one({"_id": job_id})
    if not job or job["status"] in ("completed",):
        return
    fn = HANDLERS.get(job["type"])
    if fn is None:
        await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": f"no handler for {job['type']}", "updated_at": now()}})
        return
    while True:
        job = await db.background_jobs.find_one({"_id": job_id})
        attempt = job["attempts"] + 1
        await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "processing", "attempts": attempt, "started_at": now(), "updated_at": now()}})
        try:
            await fn(db, job)
            await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "completed", "error": None, "finished_at": now(), "updated_at": now()}})
            return
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:500]}"
            log.error("job %s (%s) attempt %s failed: %s\n%s", job_id, job["type"], attempt, err, traceback.format_exc())
            if attempt >= job.get("max_attempts", MAX_ATTEMPTS):
                await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": err, "finished_at": now(), "updated_at": now()}})
                on_fail = getattr(fn, "on_final_failure", None)
                if on_fail:
                    try:
                        await on_fail(db, job, err)
                    except Exception:  # noqa: BLE001
                        log.exception("on_final_failure hook failed")
                return
            await db.background_jobs.update_one({"_id": job_id}, {"$set": {"status": "retrying", "error": err, "updated_at": now()}})
            await asyncio.sleep(min(30, 2 ** attempt))


async def recover_stuck_jobs(db, older_than_seconds: int = 900) -> int:
    """On startup: re-dispatch jobs left in processing/queued by a crashed worker."""
    from datetime import timedelta
    cutoff = now() - timedelta(seconds=older_than_seconds)
    stuck = db.background_jobs.find({"status": {"$in": ["processing", "retrying", "queued"]}, "updated_at": {"$lt": cutoff}})
    n = 0
    async for j in stuck:
        await db.background_jobs.update_one({"_id": j["_id"]}, {"$set": {"status": "queued", "updated_at": now()}})
        dispatch(j["_id"])
        n += 1
    return n
