"""Registers job handlers. Imported by the API app and the Celery worker."""
from app.services import documents, workflows  # noqa: F401
