"""Authentication, authorization and project isolation through the real API."""
from tests.conftest import as_user

A, B, ADMIN = "alice@test.local", "bob@test.local", "admin@test.local"


async def test_requires_identity(api):
    r = await api.get("/api/spaces")
    assert r.status_code == 401


async def test_user_cannot_see_others_space_or_project(api):
    s = (await api.post("/api/spaces", json={"name": "Networks"}, headers=as_user(A))).json()
    p = (await api.post("/api/projects", json={"space_id": s["id"], "name": "TCP", "learning_goal": "pass exam"}, headers=as_user(A))).json()
    assert (await api.get(f"/api/spaces/{s['id']}", headers=as_user(B))).status_code == 404
    assert (await api.get(f"/api/projects/{p['id']}", headers=as_user(B))).status_code == 404
    assert (await api.get(f"/api/projects/{p['id']}/mastery", headers=as_user(B))).status_code == 404
    assert (await api.post(f"/api/projects/{p['id']}/tutor/ask", json={"message": "hi"}, headers=as_user(B))).status_code == 404
    assert (await api.get("/api/spaces", headers=as_user(B))).json() == []
    assert (await api.get(f"/api/projects/{p['id']}", headers=as_user(A))).status_code == 200


async def test_cannot_create_project_in_others_space(api):
    s = (await api.post("/api/spaces", json={"name": "Mine"}, headers=as_user(A))).json()
    r = await api.post("/api/projects", json={"space_id": s["id"], "name": "Intruder"}, headers=as_user(B))
    assert r.status_code == 404


async def test_admin_enforced_on_backend(api):
    assert (await api.get("/api/admin/overview", headers=as_user(A))).status_code == 403
    assert (await api.get("/api/admin/overview", headers=as_user(ADMIN))).status_code == 200


async def test_validation(api):
    assert (await api.post("/api/spaces", json={"name": ""}, headers=as_user(A))).status_code == 422
    assert (await api.post("/api/spaces", json={"name": "x", "color": "red"}, headers=as_user(A))).status_code == 422


async def test_events_and_home_reflect_real_data(api):
    s = (await api.post("/api/spaces", json={"name": "S"}, headers=as_user(A))).json()
    p = (await api.post("/api/projects", json={"space_id": s["id"], "name": "P"}, headers=as_user(A))).json()
    acts = (await api.get("/api/activity", headers=as_user(A))).json()
    assert {a["type"] for a in acts} == {"space_created", "project_created"}
    home = (await api.get("/api/home", headers=as_user(A))).json()
    assert home["continue_learning"]["id"] == p["id"]
    assert home["overall"]["concepts"] == 0


def test_qdrant_filter_always_scopes_user_and_project():
    from app.services.vectorstore import project_filter
    f = project_filter("u1", "p1")
    keys = {c.key: c.match.value for c in f.must}
    assert keys == {"user_id": "u1", "project_id": "p1"}
