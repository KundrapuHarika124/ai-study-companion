"""Grounded AI Tutor: retrieval → sufficiency → structured generation → server-built citations → visual decision."""
from __future__ import annotations
import json
from app.core.errors import NotFound
from app.core.utils import new_id, now, truncate
from app.schemas import TutorLLMOutput, TutorAction
from app.services import retrieval, visuals, learner_context, events
from app.services.llm import llm, DATA_GUARD

INSUFFICIENT = ("I couldn't find enough evidence in your uploaded material to answer that reliably. "
                "Try rephrasing, or upload material that covers this topic. I can still help with anything your documents do cover.")

ACTION_TEXT: dict[TutorAction, str] = {
    "ask": "Answer the learner's question.",
    "explain_simpler": "Re-explain the most recent topic in simpler terms, with a concrete analogy, for a beginner.",
    "example": "Give one worked, concrete example of the most recent topic.",
    "hint": "Do NOT give the full answer. Give a single hint that nudges the learner toward figuring it out.",
    "visual": "Explain the most recent topic briefly and REQUEST a visual (set visual.kind appropriately).",
    "summarize": "Summarize the key points discussed so far in this conversation as a short revision list.",
    "test_me": "Ask the learner ONE question that tests their understanding of the most recent topic. Do not answer it.",
}

SYSTEM = (
    "You are a patient study tutor working inside ONE learner's project. You explain clearly, connect ideas to the learner's goal, "
    "and you are strictly grounded: use ONLY the evidence chunks provided. If the evidence does not support a reliable answer, set "
    "sufficient=false and say so plainly instead of guessing. Never invent facts, page numbers or sources. " + DATA_GUARD +
    "\nOutput JSON with keys: answer (markdown string), sufficient (bool), used_chunk_ids (array of the chunk ids you actually relied on), "
    "concept (the single main concept name, matching a project concept when possible), follow_ups (2-3 short suggested next questions), "
    "visual (object: kind one of none|sequence|layers|steps|array|network|curve|table_relation|tree, plus title and the fields for that kind: "
    "sequence→actors[] + messages[{from,to,label}]; layers→items[]; steps→items[]; array→values[] + highlights[]; network→layer_sizes[] + items[] labels; "
    "curve→items[xLabel,yLabel]; table_relation→left[] + right[] + items[joinKey]; tree→root + children{parent:[kids]}). "
    "Choose a visual ONLY when it genuinely improves understanding of a process, structure, sequence or relationship; otherwise kind='none'."
)


async def get_or_create_conversation(db, *, user: dict, project: dict, conversation_id: str | None) -> dict:
    if conversation_id:
        conv = await db.conversations.find_one({"_id": conversation_id, "project_id": project["_id"], "user_id": user["id"]})
        if not conv:
            raise NotFound("Conversation")
        return conv
    conv = {"_id": new_id(), "user_id": user["id"], "project_id": project["_id"], "title": "New conversation",
            "created_at": now(), "updated_at": now(), "message_count": 0}
    await db.conversations.insert_one(conv)
    return conv


async def ask(db, *, user: dict, project: dict, message: str, conversation_id: str | None, action: TutorAction = "ask") -> dict:
    conv = await get_or_create_conversation(db, user=user, project=project, conversation_id=conversation_id)
    user_msg = {"_id": new_id(), "conversation_id": conv["_id"], "project_id": project["_id"], "user_id": user["id"], "role": "user",
                "content": message, "action": action, "created_at": now()}
    await db.messages.insert_one(user_msg)
    if conv["message_count"] == 0:
        await db.conversations.update_one({"_id": conv["_id"]}, {"$set": {"title": truncate(message, 60)}})

    # Relevant recent turns only (not the whole history)
    history = await db.messages.find({"conversation_id": conv["_id"], "_id": {"$ne": user_msg["_id"]}}).sort("created_at", -1).limit(6).to_list(6)
    history.reverse()
    query = message
    if action != "ask" and history:
        last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        query = f"{last_user} {message}"
    evidence = await retrieval.retrieve(user_id=user["id"], project_id=project["_id"], query=query, limit=8)
    ctx = await learner_context.compose(db, project=project, task="tutor")

    if not retrieval.sufficient(evidence) and action in ("ask", "example", "visual", "explain_simpler"):
        reply = await _save_assistant(db, conv, project, user, INSUFFICIENT, citations=[], visual=None, concept="", follow_ups=[],
                                      sufficient=False, retrieval_count=len(evidence))
        await events.record(db, user_id=user["id"], type="tutor_interaction", project_id=project["_id"], space_id=project["space_id"],
                            payload={"conversation_id": conv["_id"], "sufficient": False, "action": action})
        return {"conversation_id": conv["_id"], "message": reply}

    ev_block = "\n\n".join(f"<chunk id=\"{e.chunk_id}\" source=\"{e.label}\" score=\"{e.score:.2f}\">\n{e.text}\n</chunk>" for e in evidence)
    hist_block = "\n".join(f"{m['role'].upper()}: {truncate(m['content'], 600)}" for m in history)
    prompt = (f"TASK: {ACTION_TEXT[action]}\n\nLEARNER CONTEXT:\n{ctx}\n\n"
              f"<data>\nRECENT CONVERSATION:\n{hist_block or '(none)'}\n\nLEARNER MESSAGE:\n{message}\n\nEVIDENCE FROM THE LEARNER'S MATERIALS:\n{ev_block or '(none)'}\n</data>\n\n"
              "Return the JSON object now.")
    out: TutorLLMOutput = await llm.generate_json(prompt, TutorLLMOutput, system=SYSTEM, feature="tutor", user_id=user["id"],
                                                  project_id=project["_id"], db=db, retrieval_count=len(evidence))
    # Citations are built by the server from the retrieved set: the model cannot fabricate them.
    valid = {e.chunk_id: e for e in evidence}
    used = [valid[c] for c in out.used_chunk_ids if c in valid]
    if out.sufficient and not used and evidence and action == "ask":
        used = evidence[:2]  # model answered but did not list chunks: cite the top evidence it was given
    citations = []
    seen = set()
    for e in used:
        key = (e.material_id, e.page)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"chunk_id": e.chunk_id, "material_id": e.material_id, "page": e.page, "label": e.label, "snippet": truncate(e.text, 220)})
    answer = out.answer if out.sufficient else (out.answer if "evidence" in out.answer.lower() or "material" in out.answer.lower() else INSUFFICIENT)
    if not out.sufficient:
        citations = []
    visual, vcount = (None, 0)
    if out.sufficient and (out.visual.kind != "none" or action == "visual"):
        visual, vcount = await visuals.pick_visual(db, user_id=user["id"], project_id=project["_id"], question=query, cited=citations, spec=out.visual)
    if vcount:
        last_run = await db.ai_runs.find_one({"user_id": user["id"], "project_id": project["_id"], "feature": "tutor"}, sort=[("created_at", -1)])
        if last_run:
            await db.ai_runs.update_one({"_id": last_run["_id"]}, {"$set": {"visual_retrieval_count": vcount}})
    reply = await _save_assistant(db, conv, project, user, answer, citations=citations, visual=visual, concept=out.concept,
                                  follow_ups=out.follow_ups[:3], sufficient=out.sufficient, retrieval_count=len(evidence))
    await learner_context.note_topic(db, user_id=user["id"], project_id=project["_id"], topic=out.concept)
    await events.record(db, user_id=user["id"], type="tutor_interaction", project_id=project["_id"], space_id=project["space_id"],
                        payload={"conversation_id": conv["_id"], "concept": out.concept, "sufficient": out.sufficient, "citations": len(citations),
                                 "visual": visual["source"] if visual else None, "action": action})
    return {"conversation_id": conv["_id"], "message": reply}


async def _save_assistant(db, conv, project, user, content, *, citations, visual, concept, follow_ups, sufficient, retrieval_count) -> dict:
    msg = {"_id": new_id(), "conversation_id": conv["_id"], "project_id": project["_id"], "user_id": user["id"], "role": "assistant",
           "content": content, "citations": citations, "visual": visual, "concept": concept, "follow_ups": follow_ups,
           "sufficient": sufficient, "retrieval_count": retrieval_count, "created_at": now()}
    await db.messages.insert_one(msg)
    await db.conversations.update_one({"_id": conv["_id"]}, {"$inc": {"message_count": 2}, "$set": {"updated_at": now(), "last_concept": concept}})
    m = dict(msg); m["id"] = m.pop("_id")
    return m
