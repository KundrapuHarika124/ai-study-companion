"""Adaptive quiz engine. Concept + difficulty selection uses several evidence signals, not wrong→easy / correct→hard."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.core.errors import BadRequest, NotFound
from app.core.utils import new_id, now
from app.services import assessment, mastery, events
from app.services.jobs import enqueue


DIFFS = ["easy", "medium", "hard"]


def select_concept(
    concepts: list[str],
    mastery_map: dict[str, dict],
    recent_answers: list[dict],
    asked_in_session: list[str],
    focus: str | None = None,
    seed: int | None = None,
) -> str:
    """Priority = weakness + recent-mistake rate + staleness + lack of evidence − repetition penalty."""
    if focus and focus in concepts:
        return focus

    rnd = random.Random(seed)
    ts = now()

    best, best_score = concepts[0], -1e9

    for c in concepts:
        m = mastery_map.get(c)

        mv = m["mastery"] if m else 0.5
        evidence = m["evidence_count"] if m else 0

        recent_c = [
            a for a in recent_answers
            if a["concept"] == c
        ][:5]

        mistake_rate = (
            sum(1 for a in recent_c if a["score"] < 0.5) / len(recent_c)
            if recent_c
            else 0.0
        )

        last = m.get("last_assessed_at") if m else None

        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        days = (
            (ts - last).total_seconds() / 86400
            if last
            else 30
        )

        staleness = min(1.0, days / 14)

        score = (
            0.45 * (1 - mv)
            + 0.25 * mistake_rate
            + 0.15 * staleness
            + (0.15 if evidence == 0 else 0)
        )

        score -= 0.35 * asked_in_session.count(c)
        score += rnd.random() * 0.03

        if score > best_score:
            best = c
            best_score = score

    return best


def select_difficulty(
    m: dict | None,
    recent_on_concept: list[dict],
) -> str:
    mv = m["mastery"] if m else 0.5

    d = (
        0
        if mv < 0.4
        else 1
        if mv < 0.7
        else 2
    )

    last2 = [
        a["score"]
        for a in recent_on_concept[:2]
    ]

    if len(last2) == 2 and all(s >= 0.7 for s in last2):
        d = min(2, d + 1)

    elif len(last2) == 2 and all(s < 0.5 for s in last2):
        d = max(0, d - 1)

    return DIFFS[d]


def select_type(
    index: int,
    difficulty: str,
    m: dict | None,
) -> str:
    mv = m["mastery"] if m else 0.5

    if index % 3 == 2:
        return "open"

    if difficulty == "hard" and mv >= 0.6:
        return "open"

    return "mcq"


async def start(
    db,
    *,
    user: dict,
    project: dict,
    length: int,
    focus_concept: str | None,
) -> dict:
    concepts = [
        c["name"]
        async for c in db.concepts.find({
            "project_id": project["_id"]
        })
    ]

    if not concepts:
        raise BadRequest(
            "No concepts yet. Upload and process at least one material first."
        )

    session = {
        "_id": new_id(),
        "user_id": user["id"],
        "project_id": project["_id"],
        "length": length,
        "focus_concept": focus_concept,
        "status": "active",
        "answered": 0,
        "score_sum": 0.0,
        "created_at": now(),
        "updated_at": now(),
        "finished_at": None,
    }

    await db.quiz_sessions.insert_one(session)

    await events.record(
        db,
        user_id=user["id"],
        type="quiz_started",
        project_id=project["_id"],
        space_id=project["space_id"],
        payload={
            "session_id": session["_id"],
            "length": length,
        },
    )

    q = await next_question(
        db,
        user=user,
        project=project,
        session=session,
    )

    s = dict(session)
    s["id"] = s.pop("_id")

    return {
        "session": s,
        "question": q,
    }


async def get_session(
    db,
    *,
    user: dict,
    project: dict,
    session_id: str,
) -> dict:
    s = await db.quiz_sessions.find_one({
        "_id": session_id,
        "project_id": project["_id"],
        "user_id": user["id"],
    })

    if not s:
        raise NotFound("Quiz session")

    return s


async def next_question(
    db,
    *,
    user: dict,
    project: dict,
    session: dict,
) -> dict | None:

    if session["answered"] >= session["length"]:
        return None

    pending = await db.quiz_questions.find_one({
        "session_id": session["_id"],
        "answered": False,
    })

    if pending:
        return _public_q(pending)

    # Get only the current concepts belonging to this project.
    concepts = [
        c["name"]
        async for c in db.concepts.find({
            "project_id": project["_id"]
        })
    ]

    # IMPORTANT:
    # Only use mastery records whose concept still exists
    # in the current concept list.
    mastery_map = {
        m["concept"]: m
        async for m in db.mastery.find({
            "project_id": project["_id"],
            "concept": {"$in": concepts},
        })
    }

    recent = await db.quiz_answers.find(
        {
            "project_id": project["_id"]
        }
    ).sort(
        "created_at",
        -1,
    ).limit(40).to_list(40)

    asked = [
        q["concept"]
        async for q in db.quiz_questions.find({
            "session_id": session["_id"]
        })
    ]

    concept = select_concept(
        concepts,
        mastery_map,
        recent,
        asked,
        session.get("focus_concept"),
    )

    recent_c = [
        a
        for a in recent
        if a["concept"] == concept
    ]

    difficulty = select_difficulty(
        mastery_map.get(concept),
        recent_c,
    )

    qtype = select_type(
        session["answered"],
        difficulty,
        mastery_map.get(concept),
    )

    avoid = [
        q["question"]
        async for q in db.quiz_questions.find({
            "project_id": project["_id"],
            "concept": concept,
        }).sort(
            "created_at",
            -1,
        ).limit(8)
    ]

    gen, sources = await assessment.generate_question(
        db,
        user=user,
        project=project,
        concept=concept,
        difficulty=difficulty,
        qtype=qtype,
        avoid=avoid,
    )

    doc = {
        "_id": new_id(),
        "session_id": session["_id"],
        "project_id": project["_id"],
        "user_id": user["id"],
        "index": session["answered"],
        "concept": concept,
        "difficulty": difficulty,
        "type": gen.type,
        "question": gen.question,
        "options": gen.options,
        "correct_index": gen.correct_index,
        "reference_answer": gen.reference_answer,
        "explanation": gen.explanation,
        "key_points": gen.key_points,
        "sources": sources,
        "answered": False,
        "created_at": now(),
        "selection_reason": _reason(
            mastery_map.get(concept),
            recent_c,
            difficulty,
        ),
    }

    await db.quiz_questions.insert_one(doc)

    return _public_q(doc)


def _reason(
    m,
    recent_c,
    difficulty,
) -> str:
    if not m:
        return (
            f"No evidence yet for this concept, "
            f"starting at {difficulty}."
        )

    mist = sum(
        1
        for a in recent_c[:5]
        if a["score"] < 0.5
    )

    return (
        f"Mastery {int(m['mastery'] * 100)}% "
        f"with {mist} recent mistake(s): "
        f"{difficulty} question."
    )


def _public_q(q: dict) -> dict:
    return {
        "id": q["_id"],
        "index": q["index"],
        "concept": q["concept"],
        "difficulty": q["difficulty"],
        "type": q["type"],
        "question": q["question"],
        "options": q["options"],
        "sources": q.get("sources", []),
        "selection_reason": q.get(
            "selection_reason",
            "",
        ),
    }


async def answer(
    db,
    *,
    user: dict,
    project: dict,
    session: dict,
    question_id: str,
    answer_text: str,
) -> dict:

    q = await db.quiz_questions.find_one({
        "_id": question_id,
        "session_id": session["_id"],
        "user_id": user["id"],
    })

    if not q:
        raise NotFound("Question")

    if q["answered"]:
        existing = await db.quiz_answers.find_one({
            "question_id": question_id
        })

        return {
            "result": _public_result(existing, q),
            "next_question": await next_question(
                db,
                user=user,
                project=project,
                session=session,
            ),
            "session": await _session_state(
                db,
                session["_id"],
            ),
        }

    if q["type"] == "mcq":
        try:
            idx = int(answer_text.strip())
        except ValueError:
            raise BadRequest(
                "MCQ answer must be the option index"
            )

        score = (
            1.0
            if idx == q["correct_index"]
            else 0.0
        )

        grade = {
            "score": score,
            "correct": (
                [q["options"][q["correct_index"]]]
                if score
                else []
            ),
            "missing": (
                []
                if score
                else [q["options"][q["correct_index"]]]
            ),
            "incorrect": (
                []
                if score
                else (
                    [q["options"][idx]]
                    if 0 <= idx < len(q["options"])
                    else []
                )
            ),
            "understood": "",
            "reasoning_quality": "",
            "feedback": (
                q["explanation"]
                if score
                else f"Not quite. {q['explanation']}"
            ),
        }

    else:
        g = await assessment.grade_open(
            db,
            user=user,
            project=project,
            question=q,
            answer=answer_text,
        )

        score = g.score
        grade = g.model_dump()

    ans = {
        "_id": new_id(),
        "question_id": question_id,
        "session_id": session["_id"],
        "project_id": project["_id"],
        "user_id": user["id"],
        "concept": q["concept"],
        "difficulty": q["difficulty"],
        "type": q["type"],
        "question": q["question"],
        "answer": answer_text,
        "score": score,
        "grade": grade,
        "created_at": now(),
    }

    await db.quiz_answers.insert_one(ans)

    await db.quiz_questions.update_one(
        {"_id": question_id},
        {"$set": {"answered": True}},
    )

    m = await mastery.apply_evidence(
        db,
        user_id=user["id"],
        project_id=project["_id"],
        concept=q["concept"],
        score=score,
        difficulty=q["difficulty"],
        kind=q["type"],
        source="quiz",
        ref_id=ans["_id"],
    )

    await db.quiz_sessions.update_one(
        {"_id": session["_id"]},
        {
            "$inc": {
                "answered": 1,
                "score_sum": score,
            },
            "$set": {
                "updated_at": now()
            },
        },
    )

    await events.record(
        db,
        user_id=user["id"],
        type="question_answered",
        project_id=project["_id"],
        space_id=project["space_id"],
        payload={
            "session_id": session["_id"],
            "concept": q["concept"],
            "score": score,
            "type": q["type"],
            "difficulty": q["difficulty"],
        },
        dedupe_key=f"qa:{ans['_id']}",
    )

    session = await db.quiz_sessions.find_one({
        "_id": session["_id"]
    })

    nq = None

    if session["answered"] >= session["length"]:

        await db.quiz_sessions.update_one(
            {"_id": session["_id"]},
            {
                "$set": {
                    "status": "completed",
                    "finished_at": now(),
                }
            },
        )

        await events.record(
            db,
            user_id=user["id"],
            type="assessment_completed",
            project_id=project["_id"],
            space_id=project["space_id"],
            payload={
                "session_id": session["_id"],
                "avg_score": (
                    session["score_sum"]
                    / max(1, session["answered"])
                ),
                "questions": session["answered"],
            },
            dedupe_key=f"ac:{session['_id']}",
        )

        await enqueue(
            db,
            type="post_quiz_workflow",
            payload={
                "session_id": session["_id"]
            },
            user_id=user["id"],
            project_id=project["_id"],
            idempotency_key=f"post_quiz:{session['_id']}",
        )

    else:
        nq = await next_question(
            db,
            user=user,
            project=project,
            session=session,
        )

    result = _public_result(ans, q)
    result["mastery_impact"] = m

    return {
        "result": result,
        "next_question": nq,
        "session": await _session_state(
            db,
            session["_id"],
        ),
    }


def _public_result(
    ans: dict,
    q: dict,
) -> dict:
    return {
        "question_id": q["_id"],
        "concept": q["concept"],
        "type": q["type"],
        "question": q["question"],
        "answer": ans.get("answer"),
        "score": ans["score"],
        "grade": ans["grade"],
        "correct_index": q.get("correct_index"),
        "reference_answer": q.get("reference_answer"),
        "explanation": q.get("explanation"),
        "key_points": q.get("key_points", []),
        "sources": q.get("sources", []),
    }


async def _session_state(
    db,
    session_id: str,
) -> dict:
    s = await db.quiz_sessions.find_one({
        "_id": session_id
    })

    s = dict(s)
    s["id"] = s.pop("_id")

    s["avg_score"] = (
        s["score_sum"]
        / max(1, s["answered"])
    )

    return s


async def summary(
    db,
    *,
    user: dict,
    project: dict,
    session: dict,
) -> dict:

    answers = await db.quiz_answers.find({
        "session_id": session["_id"]
    }).sort(
        "created_at",
        1,
    ).to_list(100)

    qs = {
        q["_id"]: q
        async for q in db.quiz_questions.find({
            "session_id": session["_id"]
        })
    }

    rec = await db.recommendations.find_one({
        "project_id": project["_id"],
        "trigger_ref": session["_id"],
    })

    st = await _session_state(
        db,
        session["_id"],
    )

    return {
        "session": st,
        "answers": [
            _public_result(
                a,
                qs[a["question_id"]],
            )
            for a in answers
            if a["question_id"] in qs
        ],
        "by_concept": _by_concept(answers),
        "recommendation": _pub(rec),
    }


def _by_concept(
    answers: list[dict],
) -> list[dict]:
    agg: dict[str, list[float]] = {}

    for a in answers:
        agg.setdefault(
            a["concept"],
            []
        ).append(a["score"])

    return [
        {
            "concept": c,
            "avg": sum(v) / len(v),
            "count": len(v),
        }
        for c, v in agg.items()
    ]


def _pub(d):
    if not d:
        return None

    d = dict(d)
    d["id"] = d.pop("_id")

    return d