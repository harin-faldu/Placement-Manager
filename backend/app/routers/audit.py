from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.audit import verify_chain
from app.core.database import get_db
from app.core.deps import require
from app.persistence.models import AuditLog, User
from app.services.placement import public_audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return {"items": [public_audit(row) for row in rows]}


@router.post("/verify")
def verify(
    _user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    rows = list(db.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all())
    return verify_chain(rows)
