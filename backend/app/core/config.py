"""Environment configuration. Every setting comes from the environment / .env.
Startup validation lives in `validate()` so missing configuration fails loudly and early."""
from __future__ import annotations
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("config")


class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "study_companion"

    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "study_chunks"

    REDIS_URL: str = ""
    JOB_BACKEND: str = "auto"  # celery | inline | auto

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    AI_TIMEOUT_SECONDS: int = 45
    RETRIEVAL_MIN_SCORE: float = 0.30

    AUTH_MODE: str = "firebase"  # firebase | dev
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""
    ADMIN_EMAILS: str = ""

    STORAGE_DIR: str = "./storage"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def job_backend(self) -> str:
        if self.JOB_BACKEND == "auto":
            return "celery" if self.REDIS_URL else "inline"
        return self.JOB_BACKEND

    def validate(self) -> list[str]:
        """Returns a list of warnings. Raises on fatal misconfiguration."""
        warnings: list[str] = []
        if not self.MONGODB_URI:
            raise RuntimeError("MONGODB_URI is required")
        if not self.GROQ_API_KEY:
            warnings.append(
                "GROQ_API_KEY is not set: Tutor, quiz generation, grading and recommendations "
                "will return 503 until it is configured."
            ) 
        if self.AUTH_MODE == "dev":
            warnings.append("AUTH_MODE=dev: identities come from the X-Dev-User header. NEVER use this outside local development.")
        elif not self.FIREBASE_CREDENTIALS_JSON and not self.FIREBASE_PROJECT_ID:
            warnings.append("AUTH_MODE=firebase but no FIREBASE_CREDENTIALS_JSON / FIREBASE_PROJECT_ID set; token verification will fail.")
        if self.job_backend == "celery" and not self.REDIS_URL:
            raise RuntimeError("JOB_BACKEND=celery requires REDIS_URL")
        if not self.admin_emails:
            warnings.append("ADMIN_EMAILS is empty: nobody will be able to open the admin dashboard.")
        for w in warnings:
            log.warning(w)
        return warnings


settings = Settings()
