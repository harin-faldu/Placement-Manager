from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require
from app.domain import COURSES
from app.http import client_ip, conflict, fail
from app.models import Attendance, Drive, Offer, Student, User
from app.schemas import ExclusionUpdate, StudentCreate, StudentUpdate
from app.security import encrypt_mobile, mobile_digest
from app.services import (
    attendance_dict,
    audit,
    can_read_student,
    company_map,
    coordinator_field_error,
    load_config,
    offer_dict,
    offers_for,
    profile_snapshot,
    refresh_status,
    standing_for,
    student_dict,
)
from app.validate import like_contains

router = APIRouter(prefix="/api", tags=["students"])


def _load(db: Session, user: User, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if student is None or not can_read_student(user, student):
        fail(404, "Student record not found")
    return student


def _insert_student(db: Session, body: StudentCreate) -> Student:
    student = Student(
        placement_id=body.placement_id,
        full_name=body.full_name,
        email=body.email,
        mobile_encrypted=encrypt_mobile(body.mobile),
        mobile_hash=mobile_digest(body.mobile),
        course=body.course,
        batch=body.batch,
        registration_status=body.registration_status,
        eligibility_status=body.eligibility_status,
        cgpa=body.cgpa,
        remarks=body.remarks or None,
        placement_status="unplaced",
    )
    db.add(student)
    db.flush()
    return student


@router.get("/students")
def list_students(
    q: str | None = Query(default=None, max_length=80),
    course: str | None = None,
    batch: str | None = None,
    registration_status: str | None = None,
    eligibility_status: str | None = None,
    placement_status: str | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require("admin", "officer", "coordinator")),
    db: Session = Depends(get_db),
):
    if user.role != "admin":
        include_archived = False
    filters = []
    if not include_archived:
        filters.append(Student.archived_at.is_(None))
    if user.role == "coordinator":
        if course and course != user.course:
            fail(403, "Course coordinators can view only their own programme")
        filters.append(Student.course == user.course)
    elif course:
        filters.append(Student.course == course)
    if batch:
        filters.append(Student.batch == batch)
    if registration_status:
        filters.append(Student.registration_status == registration_status)
    if eligibility_status:
        filters.append(Student.eligibility_status == eligibility_status)
    if placement_status:
        filters.append(Student.placement_status == placement_status)
    if q and q.strip():
        pattern = like_contains(q.strip())
        filters.append(
            or_(
                Student.full_name.ilike(pattern, escape="\\"),
                Student.placement_id.ilike(pattern, escape="\\"),
                Student.email.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(Student).where(*filters)) or 0
    rows = db.scalars(
        select(Student).where(*filters).order_by(Student.full_name, Student.placement_id).offset(offset).limit(limit)
    ).all()
    return {"items": [student_dict(row, user) for row in rows], "total": total}


@router.post("/students")
def create_student(
    body: StudentCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    try:
        student = _insert_student(db, body)
        audit(db, user, "student.create", "student", student.id, None, profile_snapshot(student, reveal_contact=True), client_ip(request))
        db.commit()
    except IntegrityError as exc:
        conflict(db, exc)
    return student_dict(student, user)


@router.get("/students/{student_id}")
def get_student(
    student_id: str,
    request: Request,
    user: User = Depends(require("admin", "officer", "coordinator", "student")),
    db: Session = Depends(get_db),
):
    student = _load(db, user, student_id)
    rows = offers_for(db, student.id)
    names = company_map(db, rows)
    reveal = True
    offers = [offer_dict(row, names.get(row.company_id, ""), reveal_pay=reveal) for row in rows]
    attendance_rows = db.scalars(select(Attendance).where(Attendance.student_id == student.id).order_by(Attendance.created_at.desc())).all()
    drive_ids = {row.drive_id for row in attendance_rows}
    titles = {}
    if drive_ids:
        for drive in db.scalars(select(Drive).where(Drive.id.in_(drive_ids))).all():
            titles[drive.id] = drive.title
    audit(
        db,
        user,
        "student.view",
        "student",
        student.id,
        None,
        {"contact_included": True, "compensation_included": True},
        client_ip(request),
    )
    db.commit()
    return {
        "student": student_dict(student, user),
        "offers": offers,
        "attendance": [attendance_dict(row, titles.get(row.drive_id)) for row in attendance_rows],
        "standing": standing_for(db, student),
    }


@router.patch("/students/{student_id}")
def update_student(
    student_id: str,
    body: StudentUpdate,
    request: Request,
    user: User = Depends(require("admin", "officer", "coordinator")),
    db: Session = Depends(get_db),
):
    student = _load(db, user, student_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        fail(400, "No changes were provided")
    blocked = coordinator_field_error(user, changes)
    if blocked:
        fail(403, blocked)
    before = profile_snapshot(student, reveal_contact=True)
    if "full_name" in changes and changes["full_name"]:
        student.full_name = changes["full_name"]
    if "email" in changes and changes["email"]:
        student.email = changes["email"]
    if "mobile" in changes and changes["mobile"]:
        student.mobile_encrypted = encrypt_mobile(changes["mobile"])
        student.mobile_hash = mobile_digest(changes["mobile"])
    if "course" in changes and changes["course"]:
        student.course = changes["course"]
    if "batch" in changes and changes["batch"]:
        student.batch = changes["batch"]
    if "registration_status" in changes and changes["registration_status"]:
        student.registration_status = changes["registration_status"]
    if "eligibility_status" in changes and changes["eligibility_status"]:
        student.eligibility_status = changes["eligibility_status"]
    if "cgpa" in changes:
        student.cgpa = changes["cgpa"]
    if "remarks" in changes:
        student.remarks = changes["remarks"] or None
    try:
        db.flush()
    except IntegrityError as exc:
        conflict(db, exc)
    refresh_status(db, student)
    audit(db, user, "student.update", "student", student.id, before, profile_snapshot(student, reveal_contact=True), client_ip(request))
    db.commit()
    return student_dict(student, user)


@router.post("/students/{student_id}/archive")
def archive_student(
    student_id: str,
    request: Request,
    user: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    student = _load(db, user, student_id)
    if student.archived_at is not None:
        fail(409, "This record is already archived")
    from app.clock import utcnow

    before = profile_snapshot(student, reveal_contact=False)
    student.archived_at = utcnow()
    audit(db, user, "student.archive", "student", student.id, before, profile_snapshot(student, reveal_contact=False), client_ip(request))
    db.commit()
    return student_dict(student, user)


@router.post("/students/{student_id}/restore")
def restore_student(
    student_id: str,
    request: Request,
    user: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    student = _load(db, user, student_id)
    if student.archived_at is None:
        fail(409, "This record is already active")
    before = profile_snapshot(student, reveal_contact=False)
    student.archived_at = None
    audit(db, user, "student.restore", "student", student.id, before, profile_snapshot(student, reveal_contact=False), client_ip(request))
    db.commit()
    return student_dict(student, user)


@router.post("/students/{student_id}/exclusion")
def update_exclusion(
    student_id: str,
    body: ExclusionUpdate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    student = _load(db, user, student_id)
    config = load_config(db)
    before = {"exclusion_drives_remaining": student.exclusion_drives_remaining}
    if body.action == "clear":
        student.exclusion_drives_remaining = 0
    else:
        student.exclusion_drives_remaining = int(config["absence_exclusion_drives"])
    audit(
        db,
        user,
        "student.exclusion",
        "student",
        student.id,
        before,
        {"exclusion_drives_remaining": student.exclusion_drives_remaining, "reason": body.reason, "action": body.action},
        client_ip(request),
    )
    db.commit()
    return student_dict(student, user)


@router.post("/imports/students")
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if len(raw) > 1_000_000:
        fail(413, "Import file is too large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail(422, "Import file must be UTF-8 CSV")
    reader = csv.DictReader(io.StringIO(text))
    required = {"placement_id", "full_name", "mobile", "email", "course", "batch", "registration_status", "eligibility_status"}
    if not reader.fieldnames or not required <= {name.strip() for name in reader.fieldnames}:
        fail(422, "CSV must include placement_id, full_name, mobile, email, course, batch, registration_status, eligibility_status")
    created = 0
    errors: list[dict] = []
    for index, row in enumerate(reader, start=2):
        if not any((row.get(key) or "").strip() for key in required):
            continue
        try:
            body = StudentCreate(
                placement_id=row.get("placement_id") or "",
                full_name=row.get("full_name") or "",
                mobile=row.get("mobile") or "",
                email=row.get("email") or "",
                course=row.get("course") or "",
                batch=row.get("batch") or "",
                registration_status=(row.get("registration_status") or "not_registered").strip(),
                eligibility_status=(row.get("eligibility_status") or "pending_verification").strip(),
                cgpa=float(row["cgpa"]) if (row.get("cgpa") or "").strip() else None,
                remarks=(row.get("remarks") or None),
            )
            with db.begin_nested():
                student = _insert_student(db, body)
                audit(db, user, "student.create", "student", student.id, None, {"placement_id": student.placement_id, "source": "import"}, client_ip(request))
            created += 1
        except ValidationError as exc:
            errors.append({"row": index, "message": exc.errors()[0]["msg"]})
        except IntegrityError:
            errors.append({"row": index, "message": "Placement ID, email, or mobile already exists"})
        except ValueError as exc:
            errors.append({"row": index, "message": str(exc)})
    audit(db, user, "student.import", "student", None, None, {"created": created, "errors": len(errors)}, client_ip(request))
    db.commit()
    return {"created": created, "errors": errors}


@router.get("/exports/students")
def export_students(
    request: Request,
    course: str | None = None,
    user: User = Depends(require("admin", "officer", "coordinator")),
    db: Session = Depends(get_db),
):
    filters = [Student.archived_at.is_(None)]
    if user.role == "coordinator":
        course = user.course
    if course:
        filters.append(Student.course == course)
    rows = db.scalars(select(Student).where(*filters).order_by(Student.course, Student.full_name)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "placement_id",
            "full_name",
            "email",
            "mobile",
            "course",
            "batch",
            "registration_status",
            "eligibility_status",
            "placement_status",
            "cgpa",
        ]
    )
    for student in rows:
        visible = student_dict(student, user)
        writer.writerow(
            [
                visible["placement_id"],
                visible["full_name"],
                visible["email"] or "",
                visible["mobile"] or "",
                visible["course"],
                visible["batch"],
                visible["registration_status"],
                visible["eligibility_status"],
                visible["placement_status"],
                "" if visible["cgpa"] is None else visible["cgpa"],
            ]
        )
    audit(
        db,
        user,
        "student.export",
        "student",
        None,
        None,
        {"rows": len(rows), "course": course, "includes_contact": True},
        client_ip(request),
    )
    db.commit()
    filename = f"placement-{(course or 'all').lower()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get("/meta")
def meta(_user: User = Depends(require("admin", "officer", "coordinator", "recruiter", "student"))):
    return {
        "session": "2026-27",
        "institution": "National Forensic Sciences University",
        "courses": COURSES,
    }
