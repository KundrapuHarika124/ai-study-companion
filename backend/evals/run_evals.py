"""Runs curated Tutor / grounding / isolation evaluation cases against a running API and stores results in `ai_evaluations`
so the admin dashboard can show them and regressions are visible across prompt/model/retrieval changes.

Usage:  cd backend && python -m evals.run_evals evals/cases.json  [--api http://localhost:8000]
"""
from __future__ import annotations
import argparse, asyncio, json, os, sys, time
import httpx
from app.db.mongo import get_db
from app.core.utils import new_id, now
from app.core.config import settings


def headers(cfg):
    if cfg.get("user_email"):
        return {"X-Dev-User": cfg["user_email"]}
    tok = os.environ.get("API_TOKEN", "")
    return {"Authorization": f"Bearer {tok}"}


async def ask(client, api, cfg, project_id, q):
    r = await client.post(f"{api}/api/projects/{project_id}/tutor/ask", json={"message": q}, headers=headers(cfg), timeout=120)
    r.raise_for_status()
    return r.json()["message"]


def judge(case, msg) -> dict:
    content = msg["content"]; ok = True; notes = []
    exp = case["expect"]
    if exp == "grounded":
        if not msg["sufficient"] or not msg["citations"]:
            ok = False; notes.append("expected grounded answer with citations")
        for term in case.get("must_mention", []):
            if term.lower() not in content.lower():
                ok = False; notes.append(f"missing '{term}'")
        if case.get("expect_visual") and not msg.get("visual"):
            ok = False; notes.append("expected a visual")
    elif exp in ("insufficient", "insufficient_or_refusal"):
        if msg["sufficient"] and exp == "insufficient":
            ok = False; notes.append("answered although evidence should be insufficient")
        if msg["citations"] and not msg["sufficient"]:
            ok = False; notes.append("citations present on insufficient answer")
    for term in case.get("must_not_mention", []):
        if term.lower() in content.lower():
            ok = False; notes.append(f"leaked '{term}'")
    return {"id": case["id"], "passed": ok, "notes": notes, "sufficient": msg["sufficient"], "citations": len(msg["citations"]),
            "visual": (msg.get("visual") or {}).get("source"), "answer_preview": content[:200]}


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cases"); ap.add_argument("--api", default="http://localhost:8000")
    a = ap.parse_args()
    cfg = json.load(open(a.cases))
    results = []
    async with httpx.AsyncClient() as client:
        for case in cfg["tutor"]:
            t0 = time.perf_counter()
            msg = await ask(client, a.api, cfg, cfg["project_id"], case["question"])
            r = judge(case, msg); r["latency_ms"] = int((time.perf_counter() - t0) * 1000); results.append(r)
            print(("PASS" if r["passed"] else "FAIL"), r["id"], r["notes"])
        iso = cfg.get("isolation")
        if iso and iso.get("other_project_id", "").strip("<>") and not iso["other_project_id"].startswith("<"):
            msg = await ask(client, a.api, cfg, iso["other_project_id"], iso["question"])
            r = judge({"id": "isolation", "expect": iso["expect"]}, msg); results.append(r)
            print(("PASS" if r["passed"] else "FAIL"), "isolation", r["notes"])
    passed = sum(1 for r in results if r["passed"])
    doc = {"_id": new_id(), "suite": "tutor_grounding", "model": settings.GEMINI_MODEL, "embedding_model": settings.EMBEDDING_MODEL,
           "min_score": settings.RETRIEVAL_MIN_SCORE, "total": len(results), "passed": passed, "results": results, "created_at": now()}
    await get_db().ai_evaluations.insert_one(doc)
    print(f"\n{passed}/{len(results)} passed. Stored evaluation {doc['_id']}.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
