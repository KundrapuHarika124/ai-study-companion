"""Grounding, citation validation and unsupported-question handling (LLM mocked)."""
import pytest
from app.core.utils import new_id, now
from app.schemas import TutorLLMOutput
from app.services import tutor
from app.services.retrieval import Evidence


def ev(cid, score, page=3, text="TCP uses a three-way handshake: SYN, SYN-ACK, ACK."):
    return Evidence(chunk_id=cid, material_id="mat1", title="Networking Notes", page=page, heading="TCP", text=text, score=score, type="text", concepts=["TCP"])


@pytest.fixture
def project_and_user(db):
    return {"_id": "p1", "space_id": "s1", "learning_goal": "learn networking"}, {"id": "u1", "email": "a@test.local"}


async def test_unsupported_question_returns_insufficient_without_llm(db, project_and_user, monkeypatch):
    project, user = project_and_user
    calls = []
    async def fake_retrieve(**kw):
        return [ev("c1", 0.12)]  # below threshold
    async def fake_llm(*a, **kw):
        calls.append(1)
    monkeypatch.setattr(tutor.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(tutor.llm, "generate_json", fake_llm)
    out = await tutor.ask(db, user=user, project=project, message="Explain quantum tunnelling", conversation_id=None)
    assert out["message"]["sufficient"] is False
    assert out["message"]["citations"] == []
    assert "enough evidence" in out["message"]["content"]
    assert calls == []


async def test_model_declared_insufficient_has_no_citations(db, project_and_user, monkeypatch):
    project, user = project_and_user
    async def fake_retrieve(**kw):
        return [ev("c1", 0.6)]
    async def fake_llm(*a, **kw):
        return TutorLLMOutput(answer="The material does not cover this.", sufficient=False, used_chunk_ids=["c1"])
    monkeypatch.setattr(tutor.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(tutor.llm, "generate_json", fake_llm)
    out = await tutor.ask(db, user=user, project=project, message="What about UDP?", conversation_id=None)
    assert out["message"]["sufficient"] is False and out["message"]["citations"] == []


async def test_citations_only_from_retrieved_chunks(db, project_and_user, monkeypatch):
    project, user = project_and_user
    async def fake_retrieve(**kw):
        return [ev("c1", 0.7), ev("c2", 0.5, page=4)]
    async def fake_llm(*a, **kw):
        return TutorLLMOutput(answer="SYN, SYN-ACK, ACK.", sufficient=True, used_chunk_ids=["c2", "FAKE-CHUNK"], concept="TCP handshake")
    async def no_visual(*a, **kw):
        return None, 0
    monkeypatch.setattr(tutor.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(tutor.llm, "generate_json", fake_llm)
    monkeypatch.setattr(tutor.visuals, "pick_visual", no_visual)
    out = await tutor.ask(db, user=user, project=project, message="Explain the TCP handshake", conversation_id=None)
    cites = out["message"]["citations"]
    assert [c["chunk_id"] for c in cites] == ["c2"]
    assert cites[0]["label"] == "Networking Notes — Page 4"
    assert await db.messages.count_documents({"conversation_id": out["conversation_id"]}) == 2
    ctx = await db.learner_context.find_one({"project_id": "p1"})
    assert "TCP handshake" in ctx["recent_topics"]


def test_prompt_injection_guard_present():
    from app.services.llm import DATA_GUARD
    from app.services.assessment import GEN_SYSTEM, GRADE_SYSTEM
    from app.services.recommendations import SYSTEM as REC
    for s in (tutor.SYSTEM, GEN_SYSTEM, GRADE_SYSTEM, REC):
        assert DATA_GUARD in s
