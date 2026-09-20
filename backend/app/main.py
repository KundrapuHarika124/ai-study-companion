from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.security import get_current_user
from app.db.mongo import get_db, ensure_indexes
from app.api import spaces, projects, materials, tutor, quiz, learning, admin
from app.services import vectorstore, embeddings
from app.services.jobs import recover_stuck_jobs
import app.workers.tasks  # noqa: F401  registers job handlers

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")
STARTUP_WARNINGS: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    STARTUP_WARNINGS.extend(settings.validate())
    db = get_db()
    try:
        await ensure_indexes(db)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Cannot reach MongoDB at {settings.MONGODB_URI}: {e}") from e
    try:
        vectorstore.ensure_collection(embeddings.dimension())
    except Exception as e:  # noqa: BLE001
        msg = f"Qdrant unavailable at {settings.QDRANT_URL} ({e}). Material processing and Tutor retrieval will fail until it is reachable."
        log.warning(msg); STARTUP_WARNINGS.append(msg)
    try:
        n = await recover_stuck_jobs(db)
        if n:
            log.info("re-dispatched %s stuck jobs", n)
    except Exception:  # noqa: BLE001
        log.exception("job recovery failed")
    yield


app = FastAPI(title="AI Study Companion API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.FRONTEND_ORIGIN.split(",")], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. The error has been logged."})


@app.get("/api/health")
async def health():
    return {"ok": True, "env": settings.APP_ENV, "warnings": STARTUP_WARNINGS, "ai_configured": bool(settings.GROQ_API_KEY), "auth_mode": settings.AUTH_MODE}


@app.get("/api/me")
async def me(user=Depends(get_current_user)):
    return user


for r in (spaces.router, projects.router, materials.router, tutor.router, quiz.router, learning.router, admin.router):
    app.include_router(r, prefix="/api")
