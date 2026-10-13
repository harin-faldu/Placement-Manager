from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings


def fail(status: int, message: str, **extra) -> None:
    detail: dict | str = {"message": message, **extra} if extra else message
    raise HTTPException(status_code=status, detail=detail)


def conflict(db: Session, exc: IntegrityError) -> None:
    db.rollback()
    text = str(getattr(exc, "orig", exc)).lower()
    if "placement_id" in text:
        fail(409, "This Placement ID already exists")
    if "mobile" in text:
        fail(409, "This mobile number is already in use")
    if "email" in text:
        fail(409, "This email is already in use")
    fail(409, "This record conflicts with an existing one")


def client_ip(request: Request) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
