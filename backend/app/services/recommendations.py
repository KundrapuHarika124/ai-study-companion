"""Recommendation engine: evidence in → one actionable next step out."""
from __future__ import annotations
import logging
from app.core.utils import new_id, now
from app.schemas import RecommendationOut
from app.services import learner_context, events
from app.services.llm import llm, DATA_GUARD

log = logging.getLogger("recs")
SYSTEM = ("You produce ONE specific, actionable next learning step for a learner, grounded in the evidence about their progress. "
          "Reference real concept names and real material titles/pages from the evidence. Never say generic things like 'keep studying'. " + DATA_GUARD +
          " Return ONLY JSON: {title (≤80 chars), body (2-3 sentences, mention what improved and what is still weak when known), "
          "action_type one of quiz|tutor|material|review, concept (the target concept), material_id (from evidence or null), page (int or null), rationale (one sentence citing the evidence)}.")


async def gather_evidence(db, project: dict) -> dict:
    pid = project["_id"]
    mastery = await db.mastery.find({"project_id": pid}).sort("mastery", 1).to_list(50)
    mistakes = await db.quiz_answers.find({"project_id": pid, "score": {"$lt": 0.5}}).sort("created_at", -1).limit(8).to_list(8)
    materials = await db.materials.find({"project_id": pid, "status": "ready"}).to_list(20)
    concepts = await db.concepts.find({"project_id": pid}).to_list(50)
    prev = await db.recommendations.find({"project_id": pid}).sort("created_at", -1).limit(3).to_list(3)
    recent_events = await db.activity_events.find({"project_id": pid}).sort("created_at", -1).limit(10).to_list(10)
    ctx = await learner_context.get(db, pid)
    # which material/page covers the weakest concept
    weakest = mastery[0]["concept"] if mastery else (concepts[0]["name"] if concepts else "")
    chunk = await db.material_chunks.find_one({"project_id": pid, "concepts": weakest}) if weakest else None
    return {"mastery": mastery, "mistakes": mistakes, "materials": materials, "concepts": concepts, "previous": prev,
            "recent_events": recent_events, "context": ctx, "weakest": weakest, "weak_chunk": chunk}


def fallback(ev: dict, project: dict) -> RecommendationOut:
    """Deterministic recommendation when the LLM is unavailable: still evidence-based."""
    if not ev["concepts"]:
        return RecommendationOut(title="Add your first study material", body="Upload a PDF so the companion can build knowledge, then ask the Tutor a question about it.",
                                 action_type="material", rationale="No materials processed yet.")
    if not ev["mastery"]:
        c = ev["concepts"][0]["name"]
        return RecommendationOut(title=f"Take a first quiz on {c}", body=f"There is no evidence of your understanding yet. A short quiz on {c} will establish a baseline for mastery tracking.",
                                 action_type="quiz", concept=c, rationale="No assessment evidence exists yet.")
    w = ev["mastery"][0]
    chunk = ev["weak_chunk"]
    mat = next((m for m in ev["materials"] if chunk and m["_id"] == chunk["material_id"]), None)
    where = f" Start with {mat['title']} page {chunk['page']}." if mat and chunk else ""
    return RecommendationOut(title=f"Review {w['concept']}, then retest", body=f"Your mastery of {w['concept']} is estimated at {int(w['mastery']*100)}%.{where} After reviewing, take a 5-question quiz focused on it.",
                             action_type="material" if mat else "quiz", concept=w["concept"], material_id=mat["_id"] if mat else None,
                             page=chunk["page"] if chunk else None, rationale=f"Lowest mastery concept ({int(w['mastery']*100)}%).")


async def generate(db, *, user: dict, project: dict, trigger: str, trigger_ref: str | None = None) -> dict:
    existing = await db.recommendations.find_one({"project_id": project["_id"], "trigger_ref": trigger_ref}) if trigger_ref else None
    if existing:
        return existing  # idempotent per trigger
    ev = await gather_evidence(db, project)
    rec: RecommendationOut
    if llm.available and ev["concepts"]:
        lines = [f"- {m['concept']}: mastery {int(m['mastery']*100)}% over {m['evidence_count']} answers" for m in ev["mastery"][:8]]
        mist = [f"- [{m['concept']}] Q: {m['question'][:120]} | learner: {str(m['answer'])[:80]}" for m in ev["mistakes"][:5]]
        mats = [f"- {m['title']} (id={m['_id']}, {m['page_count']} pages, concepts: {', '.join(m.get('concepts', [])[:6])})" for m in ev["materials"]]
        prev = [f"- {p['title']}" for p in ev["previous"]]
        rm = ev["context"].get("repeated_mistakes", [])
        prompt = (f"<data>\nGOAL: {project.get('learning_goal') or 'not specified'}\n\nMASTERY:\n" + ("\n".join(lines) or "(no evidence)") +
                  "\n\nRECENT MISTAKES:\n" + ("\n".join(mist) or "(none)") + "\n\nREPEATED MISTAKE PATTERNS:\n" + ("\n".join(str(r.get('summary', r)) for r in rm) or "(none)") +
                  "\n\nMATERIALS:\n" + ("\n".join(mats) or "(none)") + (f"\nSection covering weakest concept '{ev['weakest']}': {ev['weak_chunk']['heading'] or ''} page {ev['weak_chunk']['page']} of material id={ev['weak_chunk']['material_id']}" if ev['weak_chunk'] else "") +
                  "\n\nPREVIOUS RECOMMENDATIONS (do not repeat verbatim):\n" + ("\n".join(prev) or "(none)") + f"\n\nTRIGGER: {trigger}\n</data>\nReturn the JSON.")
        try:
            rec = await llm.generate_json(prompt, RecommendationOut, system=SYSTEM, feature="recommendation", user_id=user["id"], project_id=project["_id"], db=db)
            valid_ids = {m["_id"] for m in ev["materials"]}
            if rec.material_id and rec.material_id not in valid_ids:
                rec.material_id = None  # model may not invent material references
        except Exception as e:  # noqa: BLE001
            log.warning("LLM recommendation failed, using fallback: %s", e)
            rec = fallback(ev, project)
    else:
        rec = fallback(ev, project)
    await db.recommendations.update_many({"project_id": project["_id"], "status": "active"}, {"$set": {"status": "superseded"}})
    doc = {"_id": new_id(), "user_id": user["id"], "project_id": project["_id"], "space_id": project["space_id"], **rec.model_dump(),
           "trigger": trigger, "trigger_ref": trigger_ref, "status": "active", "created_at": now()}
    await db.recommendations.insert_one(doc)
    await events.record(db, user_id=user["id"], type="recommendation_generated", project_id=project["_id"], space_id=project["space_id"],
                        payload={"recommendation_id": doc["_id"], "title": rec.title, "concept": rec.concept})
    return doc


async def current(db, project_id: str) -> dict | None:
    return await db.recommendations.find_one({"project_id": project_id, "status": "active"}, sort=[("created_at", -1)])
