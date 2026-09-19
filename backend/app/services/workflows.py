"""Event-driven learning workflows (run as background jobs, idempotent per trigger)."""
from __future__ import annotations
from app.core.utils import now
from app.services import learner_context, recommendations, events
from app.services.jobs import handler


async def detect_repeated_mistakes(db, project_id: str) -> list[dict]:
    """A concept with ≥2 wrong answers among its last 4 attempts is a repeated-mistake pattern."""
    pipeline = [{"$match": {"project_id": project_id}}, {"$sort": {"created_at": -1}},
                {"$group": {"_id": "$concept", "scores": {"$push": "$score"}, "questions": {"$push": "$question"}}}]
    patterns = []
    async for g in db.quiz_answers.aggregate(pipeline):
        last = g["scores"][:4]
        wrong = sum(1 for s in last if s < 0.5)
        if wrong >= 2:
            patterns.append({"concept": g["_id"], "wrong": wrong, "of": len(last),
                             "summary": f"{g['_id']}: {wrong} of last {len(last)} answers incorrect", "example": g["questions"][0][:140], "detected_at": now()})
    return patterns


@handler("post_quiz_workflow")
async def post_quiz_workflow(db, job: dict) -> None:
    sid = job["payload"]["session_id"]
    session = await db.quiz_sessions.find_one({"_id": sid})
    if not session:
        return
    project = await db.projects.find_one({"_id": session["project_id"]})
    user = await db.users.find_one({"_id": session["user_id"]})
    if not project or not user:
        return
    user = {"id": user["_id"], "email": user.get("email", "")}
    # 1) weak-concept detection + strengths
    mastery = await db.mastery.find({"project_id": project["_id"]}).to_list(200)
    weak = [m["concept"] for m in mastery if m["mastery"] < 0.6 and m["evidence_count"] >= 1]
    strong = [m["concept"] for m in mastery if m["mastery"] >= 0.75 and m["evidence_count"] >= 2]
    # 2) repeated mistakes → learner context
    patterns = await detect_repeated_mistakes(db, project["_id"])
    await learner_context.update(db, user_id=user["id"], project_id=project["_id"], weaknesses=weak, strengths=strong, repeated_mistakes=patterns)
    if patterns:
        for p in patterns:
            await events.record(db, user_id=user["id"], type="repeated_mistake_detected", project_id=project["_id"], space_id=project["space_id"],
                                payload=p, dedupe_key=f"rm:{sid}:{p['concept']}")
    # 3) recommendation (idempotent per session)
    await recommendations.generate(db, user=user, project=project, trigger="quiz_completed", trigger_ref=sid)
