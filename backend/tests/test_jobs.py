import asyncio
import pytest
from app.services import jobs


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    async def nosleep(*a, **k):
        return None
    monkeypatch.setattr(jobs.asyncio, "sleep", nosleep)
    monkeypatch.setattr(jobs, "dispatch", lambda job_id: None)  # run manually in tests


async def test_enqueue_is_idempotent(db):
    a = await jobs.enqueue(db, type="t", payload={}, user_id="u", idempotency_key="k1")
    b = await jobs.enqueue(db, type="t", payload={}, user_id="u", idempotency_key="k1")
    assert a["_id"] == b["_id"]
    assert await db.background_jobs.count_documents({}) == 1


async def test_retry_then_fail_calls_hook(db):
    seen = {"n": 0, "hook": None}
    async def failing(db_, job):
        seen["n"] += 1
        raise RuntimeError("boom")
    async def hook(db_, job, err):
        seen["hook"] = err
    failing.on_final_failure = hook
    jobs.HANDLERS["failing"] = failing
    j = await jobs.enqueue(db, type="failing", payload={}, user_id="u", idempotency_key="k2")
    await jobs.run_job(j["_id"], db)
    doc = await db.background_jobs.find_one({"_id": j["_id"]})
    assert doc["status"] == "failed" and doc["attempts"] == jobs.MAX_ATTEMPTS and seen["n"] == jobs.MAX_ATTEMPTS
    assert "boom" in seen["hook"]


async def test_success_and_re_enqueue_after_failure(db):
    state = {"fail_once": True}
    async def flaky(db_, job):
        if state["fail_once"]:
            state["fail_once"] = False
            raise RuntimeError("transient")
    jobs.HANDLERS["flaky"] = flaky
    j = await jobs.enqueue(db, type="flaky", payload={}, user_id="u", idempotency_key="k3")
    await jobs.run_job(j["_id"], db)
    doc = await db.background_jobs.find_one({"_id": j["_id"]})
    assert doc["status"] == "completed" and doc["attempts"] == 2
    # completed jobs are not re-run
    await jobs.run_job(j["_id"], db)
    assert (await db.background_jobs.find_one({"_id": j["_id"]}))["attempts"] == 2
    # a new request with the same key after a terminal state re-creates work (explicit retry)
    j2 = await jobs.enqueue(db, type="flaky", payload={}, user_id="u", idempotency_key="k3")
    assert j2["status"] == "queued" and j2["_id"] == j["_id"]
