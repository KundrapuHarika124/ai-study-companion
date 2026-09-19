from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.core.utils import public, public_list
from app.db.mongo import get_db
from app.schemas import TutorAsk
from app.services import ownership, tutor

router = APIRouter(prefix="/projects/{project_id}/tutor", tags=["tutor"])


@router.get("/conversations")
async def conversations(project_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    return public_list(await db.conversations.find({"project_id": project_id}).sort("updated_at", -1).limit(30).to_list(30))


@router.get("/conversations/{conversation_id}")
async def conversation(project_id: str, conversation_id: str, user=Depends(get_current_user)):
    db = get_db()
    await ownership.get_project(db, user["id"], project_id)
    conv = await tutor.get_or_create_conversation(db, user=user, project={"_id": project_id}, conversation_id=conversation_id)
    msgs = await db.messages.find({"conversation_id": conv["_id"]}).sort("created_at", 1).limit(200).to_list(200)
    return {"conversation": public(conv), "messages": public_list(msgs)}


@router.post("/ask")
async def ask(project_id: str, body: TutorAsk, user=Depends(get_current_user)):
    db = get_db()
    project = await ownership.get_project(db, user["id"], project_id)
    return await tutor.ask(db, user=user, project=project, message=body.message, conversation_id=body.conversation_id, action=body.action)
