from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.core.utils import public_list
from app.db.mongo import get_db
from app.schemas import QuizStart, QuizAnswer
from app.services import ownership, quiz

router = APIRouter(prefix="/projects/{project_id}/quiz", tags=["quiz"])


@router.post("/start")
async def start(project_id: str, body: QuizStart, user=Depends(get_current_user)):
    db = get_db()
    project = await ownership.get_project(db, user["id"], project_id)
    return await quiz.start(db, user=user, project=project, length=body.length, focus_concept=body.focus_concept)


@router.get("/sessions")
async def sessions(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return public_list(await db.quiz_sessions.find({"project_id": project_id}).sort("created_at", -1).limit(30).to_list(30))


@router.get("/sessions/{session_id}")
async def session(project_id: str, session_id: str, user=Depends(get_current_user)):
    db = get_db()
    project = await ownership.get_project(db, user["id"], project_id)
    s = await quiz.get_session(db, user=user, project=project, session_id=session_id)
    if s["status"] == "completed":
        return {"status": "completed", **(await quiz.summary(db, user=user, project=project, session=s))}
    return {"status": "active", "session": await quiz._session_state(db, s["_id"]), "question": await quiz.next_question(db, user=user, project=project, session=s)}


@router.post("/sessions/{session_id}/answer")
async def answer(project_id: str, session_id: str, body: QuizAnswer, user=Depends(get_current_user)):
    db = get_db()
    project = await ownership.get_project(db, user["id"], project_id)
    s = await quiz.get_session(db, user=user, project=project, session_id=session_id)
    return await quiz.answer(db, user=user, project=project, session=s, question_id=body.question_id, answer_text=body.answer)
