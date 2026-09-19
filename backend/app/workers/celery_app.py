"""Celery worker entry point. Run with:  celery -A app.workers.celery_app worker --loglevel=info"""
from __future__ import annotations
import asyncio
from celery import Celery
from app.core.config import settings

celery = Celery("study_companion", broker=settings.REDIS_URL or "redis://localhost:6379/0", backend=None)
celery.conf.task_acks_late = True
celery.conf.worker_prefetch_multiplier = 1


@celery.task(name="jobs.run", bind=True, max_retries=0)
def run_job_task(self, job_id: str):
    import app.workers.tasks  # noqa: F401  (registers handlers)
    from app.services.jobs import run_job
    asyncio.run(run_job(job_id))
