import os
os.environ.update({"AUTH_MODE": "dev", "JOB_BACKEND": "inline", "REDIS_URL": "", "GEMINI_API_KEY": "", "ADMIN_EMAILS": "admin@test.local",
                   "MONGODB_URI": "mongodb://localhost:27017", "DATABASE_NAME": "test_db"})
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from app.db.mongo import set_db_override


@pytest_asyncio.fixture(autouse=True)
async def db():
    client = AsyncMongoMockClient()
    database = client["test_db"]
    set_db_override(database)
    yield database
    set_db_override(None)


@pytest_asyncio.fixture
async def api():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def as_user(email: str) -> dict:
    return {"X-Dev-User": email}
