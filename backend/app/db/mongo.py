"""Mongo access. One client per event loop (Celery tasks run their own loop)."""
from __future__ import annotations
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

_clients: dict[int, AsyncIOMotorClient] = {}
_override: AsyncIOMotorDatabase | None = None  # tests inject a mock db here


def set_db_override(db):
    global _override
    _override = db


def get_db() -> AsyncIOMotorDatabase:
    if _override is not None:
        return _override
    loop = asyncio.get_event_loop()
    key = id(loop)
    if key not in _clients:
        _clients[key] = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _clients[key][settings.DATABASE_NAME]


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.spaces.create_index([("user_id", 1), ("updated_at", -1)])
    await db.projects.create_index([("user_id", 1), ("space_id", 1)])
    await db.projects.create_index([("user_id", 1), ("last_activity_at", -1)])
    await db.materials.create_index([("project_id", 1), ("created_at", -1)])
    await db.material_chunks.create_index([("project_id", 1), ("material_id", 1), ("page", 1)])
    await db.material_chunks.create_index([("chunk_id", 1)], unique=True)
    await db.visual_assets.create_index([("project_id", 1), ("material_id", 1), ("page", 1)])
    await db.concepts.create_index([("project_id", 1), ("name", 1)], unique=True)
    await db.conversations.create_index([("project_id", 1), ("updated_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.quiz_sessions.create_index([("project_id", 1), ("created_at", -1)])
    await db.quiz_questions.create_index([("session_id", 1), ("index", 1)])
    await db.quiz_answers.create_index([("project_id", 1), ("concept", 1), ("created_at", -1)])
    await db.mastery.create_index([("project_id", 1), ("concept", 1)], unique=True)
    await db.mastery_history.create_index([("project_id", 1), ("concept", 1), ("created_at", 1)])
    await db.recommendations.create_index([("project_id", 1), ("created_at", -1)])
    await db.learner_context.create_index([("project_id", 1)], unique=True)
    await db.activity_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.activity_events.create_index([("project_id", 1), ("created_at", -1)])
    await db.activity_events.create_index([("dedupe_key", 1)], unique=True, sparse=True)
    await db.ai_runs.create_index([("created_at", -1)])
    await db.ai_runs.create_index([("user_id", 1), ("project_id", 1), ("created_at", -1)])
    await db.background_jobs.create_index([("idempotency_key", 1)], unique=True)
    await db.background_jobs.create_index([("status", 1), ("updated_at", -1)])
    await db.users.create_index([("email", 1)])
