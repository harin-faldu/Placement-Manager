from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require
from app.core.http import client_ip, conflict, fail
from app.persistence.models import Company, Student, User
from app.persistence.schemas import UserCreate, UserPatch
from app.core.security import hash_password, password_problems
from app.services.placement import audit, user_public

router = APIRouter(prefix="/api/users", tags=["users"])


def _check_links(db: Session, role: str, course: str | None, company_id: str | None, student_id: str | None) -> None:
    if role == "coordinator" and not course:
        fail(422, "A course coordinator must be assigned to one programme")
    if role == "recruiter":
        if not company_id or db.get(Company, company_id) is None:
            fail(422, "A recruiter must be linked to a company")
    if role == "student":
        student = db.get(Student, student_id) if student_id else None
        if student is None:
            fail(422, "A student account must be linked to a student record")
        existing = db.scalar(select(User).where(User.student_id == student.id))
        if existing:
            fail(409, "That student record already has an account")


@router.get("")
def list_users(_user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.role, User.full_name)).all()
    return {"items": [user_public(row) for row in rows]}


@router.post("")
def create_user(
    body: UserCreate,
    request: Request,
    user: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    problem = password_problems(body.password)
    if problem:
        fail(422, problem)
    _check_links(db, body.role, body.course, body.company_id, body.student_id)
    linked = db.get(Student, body.student_id) if body.role == "student" and body.student_id else None
    account = User(
        email=linked.email if linked else body.email,
        password_hash=hash_password(body.password),
        full_name=linked.full_name if linked else body.full_name,
        role=body.role,
        course=body.course if body.role == "coordinator" else None,
        company_id=body.company_id if body.role == "recruiter" else None,
        student_id=body.student_id if body.role == "student" else None,
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        conflict(db, exc)
    audit(
        db,
        user,
        "user.create",
        "user",
        account.id,
        None,
        {"email": account.email, "role": account.role, "course": account.course},
        client_ip(request),
    )
    db.commit()
    return user_public(account)


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    body: UserPatch,
    request: Request,
    actor: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    account = db.get(User, user_id)
    if account is None:
        fail(404, "Account not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        fail(400, "No changes were provided")
    if account.id == actor.id and changes.get("is_active") is False:
        fail(409, "You cannot deactivate your own account")
    before = {"role": account.role, "is_active": account.is_active, "course": account.course, "company_id": account.company_id}
    if "is_active" in changes and changes["is_active"] is not None:
        account.is_active = changes["is_active"]
    if "role" in changes and changes["role"]:
        account.role = changes["role"]
    if "course" in changes:
        account.course = changes["course"]
    if "company_id" in changes:
        account.company_id = changes["company_id"]
    if account.role == "coordinator" and not account.course:
        fail(422, "A course coordinator must be assigned to one programme")
    if account.role == "recruiter" and (not account.company_id or db.get(Company, account.company_id) is None):
        fail(422, "A recruiter must be linked to a company")
    audit(db, actor, "user.update", "user", account.id, before, {"role": account.role, "is_active": account.is_active, "course": account.course, "company_id": account.company_id}, client_ip(request))
    db.commit()
    return user_public(account)


@router.post("/{user_id}/reset-mfa")
def reset_mfa(
    user_id: str,
    request: Request,
    actor: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    account = db.get(User, user_id)
    if account is None:
        fail(404, "Account not found")
    account.mfa_enabled = False
    account.mfa_secret = None
    audit(db, actor, "user.reset_mfa", "user", account.id, None, {"mfa_enabled": False}, client_ip(request))
    db.commit()
    return user_public(account)
