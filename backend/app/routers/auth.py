from __future__ import annotations

from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.clock import utcnow
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.http import client_ip, fail
from app.models import LoginAttempt, MfaChallenge, User, UserSession
from app.schemas import LoginRequest, MfaConfirm, MfaRequest
from app.security import hash_token, new_token, verify_password
from app.services import audit, user_public

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _too_many(db: Session, email: str, ip: str) -> bool:
    since = utcnow() - timedelta(minutes=15)
    count = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.email == email,
            LoginAttempt.ip == ip,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
    )
    return bool(count and count >= 5)


def _attempt(db: Session, email: str, ip: str, success: bool) -> None:
    db.add(LoginAttempt(email=email, ip=ip, success=success))


def _cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_hours * 3600,
        path="/",
    )


def _open_session(db: Session, user: User, request: Request, response: Response) -> None:
    token = new_token()
    now = utcnow()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + timedelta(hours=settings.session_hours),
            last_seen_at=now,
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:200] or None,
        )
    )
    _cookie(response, token)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if _too_many(db, body.email, ip):
        fail(429, "Too many sign-in attempts. Wait 15 minutes and try again")
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        _attempt(db, body.email, ip, False)
        write_audit(
            db,
            actor_id=user.id if user else None,
            actor_email=body.email,
            actor_role=user.role if user else None,
            action="auth.login_failed",
            entity_type="user",
            entity_id=user.id if user else None,
            before=None,
            after={"result": "rejected"},
            ip=ip,
        )
        db.commit()
        fail(401, "That email or password is not valid")
    _attempt(db, body.email, ip, True)
    if user.mfa_enabled:
        challenge = new_token()
        db.add(
            MfaChallenge(
                user_id=user.id,
                token_hash=hash_token(challenge),
                expires_at=utcnow() + timedelta(minutes=5),
            )
        )
        audit(db, user, "auth.mfa_challenge", "user", user.id, None, None, ip)
        db.commit()
        return {"mfa_required": True, "challenge": challenge}
    audit(db, user, "auth.login", "user", user.id, None, {"result": "signed_in"}, ip)
    _open_session(db, user, request, response)
    db.commit()
    return {"user": user_public(user)}


@router.post("/mfa")
def confirm_mfa(body: MfaRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    row = db.scalar(select(MfaChallenge).where(MfaChallenge.token_hash == hash_token(body.challenge)))
    if row is None or row.used or row.expires_at <= utcnow():
        fail(401, "That sign-in step has expired. Start again")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active or not user.mfa_secret:
        fail(401, "That sign-in step has expired. Start again")
    if not pyotp.TOTP(user.mfa_secret).verify(body.code.strip(), valid_window=1):
        audit(db, user, "auth.mfa_failed", "user", user.id, None, None, ip)
        db.commit()
        fail(401, "That verification code is not valid")
    row.used = True
    audit(db, user, "auth.login", "user", user.id, None, {"result": "signed_in", "mfa": True}, ip)
    _open_session(db, user, request, response)
    db.commit()
    return {"user": user_public(user)}


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = request.cookies.get(settings.cookie_name)
    if token:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
    audit(db, user, "auth.logout", "user", user.id, None, None, client_ip(request))
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_public(user)}


@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="NFSU Placement Cell")
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/mfa/confirm")
def mfa_confirm(body: MfaConfirm, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(body.code.strip(), valid_window=1):
        fail(422, "That verification code is not valid")
    user.mfa_enabled = True
    audit(db, user, "auth.mfa_enabled", "user", user.id, {"mfa_enabled": False}, {"mfa_enabled": True}, client_ip(request))
    db.commit()
    return {"user": user_public(user)}
