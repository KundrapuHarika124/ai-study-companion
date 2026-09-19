"""Authentication and authorization.

Identity is derived from the request (Firebase ID token), never from a user_id in the body.
AUTH_MODE=dev accepts an `X-Dev-User: <email>` header for local development only.
"""
from __future__ import annotations
import json
import logging
import os
from fastapi import Depends, Header, HTTPException, Request
from app.core.config import settings
from app.core.utils import now
from app.db.mongo import get_db

log = logging.getLogger("auth")
_firebase_ready = False


def _init_firebase():
    global _firebase_ready
    if _firebase_ready:
        return
    import firebase_admin
    from firebase_admin import credentials
    cred = None
    raw = settings.FIREBASE_CREDENTIALS_JSON
    if raw:
        if os.path.exists(raw):
            cred = credentials.Certificate(raw)
        elif raw.strip().startswith("{"):
            cred = credentials.Certificate(json.loads(raw))
    options = {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, options) if cred else firebase_admin.initialize_app(options=options)
    _firebase_ready = True


async def _resolve_identity(request: Request, x_dev_user: str | None) -> dict:
    if settings.AUTH_MODE == "dev":
        if not x_dev_user:
            raise HTTPException(401, "Missing X-Dev-User header (AUTH_MODE=dev)")
        email = x_dev_user.strip().lower()
        return {"uid": "dev-" + email.replace("@", "-at-").replace(".", "-"), "email": email, "name": email.split("@")[0]}
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = auth[7:]
    try:
        _init_firebase()
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
    except Exception as e:  # noqa: BLE001
        log.info("token verification failed: %s", e)
        raise HTTPException(401, "Invalid or expired token")
    return {"uid": decoded["uid"], "email": (decoded.get("email") or "").lower(), "name": decoded.get("name") or (decoded.get("email") or "").split("@")[0]}


async def get_current_user(request: Request, x_dev_user: str | None = Header(default=None)) -> dict:
    ident = await _resolve_identity(request, x_dev_user)
    db = get_db()
    is_admin = ident["email"] in settings.admin_emails
    ts = now()
    await db.users.update_one(
        {"_id": ident["uid"]},
        {"$set": {"email": ident["email"], "name": ident["name"], "is_admin": is_admin, "last_seen_at": ts},
         "$setOnInsert": {"created_at": ts}},
        upsert=True,
    )
    return {"id": ident["uid"], "email": ident["email"], "name": ident["name"], "is_admin": is_admin}


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return user
