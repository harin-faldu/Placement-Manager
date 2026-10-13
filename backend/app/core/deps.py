from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import settings
from app.core.database import get_db
from app.core.http import fail
from app.persistence.models import User, UserSession
from app.core.security import hash_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        fail(401, "Sign in to continue")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = utcnow()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        fail(401, "Sign in to continue")
    idle = timedelta(minutes=settings.idle_minutes)
    if now - session.last_seen_at > idle:
        session.revoked_at = now
        db.commit()
        fail(401, "Your session timed out. Sign in again")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        fail(401, "Sign in to continue")
    session.last_seen_at = now
    db.commit()
    return user


def require(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            fail(403, "You do not have access to this action")
        return user

    return dependency
