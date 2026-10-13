from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require
from app.domain import course_short
from app.http import client_ip, conflict, fail
from app.models import Application, Attendance, Company, Drive, ExclusionCharge, Student, User
from app.policy import evaluate
from app.schemas import ApplicationCreate, AttendanceCreate, AttendanceReview, CompanyCreate, DriveCreate
from app.services import (
    attendance_dict,
    audit,
    classify_drive,
    drive_dict,
    drive_snap,
    explain_drive,
    load_config,
    open_flag,
    pending_absence_ids,
    snaps_for,
    student_snap,
    validate_package,
)
from app.validate import round_money

router = APIRouter(prefix="/api", tags=["recruitment"])


def _drive_for(user: User, drive: Drive | None) -> Drive:
    if drive is None:
        fail(404, "Drive not found")
    if user.role == "recruiter" and drive.company_id != user.company_id:
        fail(404, "Drive not found")
    return drive


@router.get("/companies")
def list_companies(user: User = Depends(require("admin", "officer", "recruiter")), db: Session = Depends(get_db)):
    stmt = select(Company).order_by(Company.name)
    if user.role == "recruiter":
        stmt = stmt.where(Company.id == user.company_id)
    rows = db.scalars(stmt).all()
    return {"items": [{"id": row.id, "name": row.name, "notes": row.notes} for row in rows]}


@router.post("/companies")
def create_company(
    body: CompanyCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    company = Company(name=body.name, notes=body.notes or None)
    db.add(company)
    try:
        db.flush()
    except IntegrityError as exc:
        conflict(db, exc)
    audit(db, user, "company.create", "company", company.id, None, {"name": company.name}, client_ip(request))
    db.commit()
    return {"id": company.id, "name": company.name, "notes": company.notes}


@router.get("/drives")
def list_drives(user: User = Depends(require("admin", "officer", "recruiter", "coordinator")), db: Session = Depends(get_db)):
    stmt = select(Drive, Company).join(Company, Company.id == Drive.company_id).order_by(Drive.created_at.desc())
    if user.role == "recruiter":
        stmt = stmt.where(Drive.company_id == user.company_id)
    rows = db.execute(stmt).all()
    return {"items": [drive_dict(drive, company.name) for drive, company in rows]}


@router.post("/drives")
def create_drive(
    body: DriveCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    company = db.get(Company, body.company_id)
    if company is None:
        fail(404, "Company not found")
    validate_package(body.offer_type, body.ctc_lpa, body.stipend_amount, body.stipend_period)
    drive = Drive(
        company_id=company.id,
        title=body.title,
        offer_type=body.offer_type,
        ctc_lpa=round_money(body.ctc_lpa),
        stipend_amount=round_money(body.stipend_amount),
        stipend_period=body.stipend_period,
        acceptance_hours=body.acceptance_hours,
        courses_json=json.dumps(body.courses),
        min_cgpa=body.min_cgpa,
        scheduled_on=body.scheduled_on,
        notes=body.notes or None,
    )
    db.add(drive)
    db.flush()
    audit(db, user, "drive.create", "drive", drive.id, None, {"title": drive.title, "offer_type": drive.offer_type}, client_ip(request))
    db.commit()
    return drive_dict(drive, company.name)


@router.get("/drives/{drive_id}/candidates")
def candidates(
    drive_id: str,
    user: User = Depends(require("admin", "officer", "recruiter")),
    db: Session = Depends(get_db),
):
    drive = _drive_for(user, db.get(Drive, drive_id))
    allowed, withheld = classify_drive(db, drive, load_config(db))
    items = []
    for student in sorted(allowed, key=lambda row: row.full_name):
        if user.role == "recruiter":
            items.append(
                {
                    "full_name": student.full_name,
                    "course_short": course_short(student.course),
                    "batch": student.batch,
                    "cgpa": student.cgpa,
                }
            )
        else:
            items.append(
                {
                    "id": student.id,
                    "placement_id": student.placement_id,
                    "full_name": student.full_name,
                    "course_short": course_short(student.course),
                    "batch": student.batch,
                    "cgpa": student.cgpa,
                }
            )
    return {"eligible": items, "eligible_count": len(allowed), "withheld_count": len(withheld)}


@router.get("/drives/{drive_id}/precheck")
def precheck(
    drive_id: str,
    user: User = Depends(require("admin", "officer", "coordinator")),
    db: Session = Depends(get_db),
):
    drive = db.get(Drive, drive_id)
    if drive is None:
        fail(404, "Drive not found")
    course = user.course if user.role == "coordinator" else None
    items = explain_drive(db, drive, load_config(db), course)
    return {
        "drive_id": drive.id,
        "title": drive.title,
        "allow": sum(1 for item in items if item["verdict"] == "allow"),
        "review": sum(1 for item in items if item["verdict"] == "review"),
        "block": sum(1 for item in items if item["verdict"] == "block"),
        "items": items,
    }


@router.post("/drives/{drive_id}/applications")
def apply_to_drive(
    drive_id: str,
    body: ApplicationCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    drive = db.get(Drive, drive_id)
    if drive is None:
        fail(404, "Drive not found")
    student = db.get(Student, body.student_id)
    if student is None:
        fail(404, "Student record not found")
    config = load_config(db)
    pending = student.id in pending_absence_ids(db, [student.id])
    evaluation = evaluate(student_snap(student, pending), snaps_for(db, student), drive_snap(drive), config)
    absence = next((check for check in evaluation.checks if check.code == "absence" and check.status == "fail"), None)
    if absence is not None:
        charged = db.scalar(
            select(ExclusionCharge).where(ExclusionCharge.student_id == student.id, ExclusionCharge.drive_id == drive.id)
        )
        if charged is None and student.exclusion_drives_remaining > 0:
            student.exclusion_drives_remaining -= 1
            db.add(ExclusionCharge(student_id=student.id, drive_id=drive.id))
    if evaluation.verdict == "review":
        open_flag(
            db,
            student_id=student.id,
            kind="participation_review",
            message=f"Participation in {drive.title} was referred for review.",
            drive_id=drive.id,
        )
    application = Application(drive_id=drive.id, student_id=student.id, verdict=evaluation.verdict, created_by=user.id)
    db.add(application)
    db.flush()
    audit(
        db,
        user,
        "application.decide",
        "application",
        application.id,
        None,
        {"verdict": evaluation.verdict, "student_id": student.id, "drive_id": drive.id},
        client_ip(request),
    )
    db.commit()
    return {"application_id": application.id, "evaluation": evaluation.as_dict()}


@router.post("/drives/{drive_id}/attendance")
def record_attendance(
    drive_id: str,
    body: AttendanceCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    drive = db.get(Drive, drive_id)
    if drive is None:
        fail(404, "Drive not found")
    student = db.get(Student, body.student_id)
    if student is None or student.archived_at is not None:
        fail(404, "Student record not found")
    courses = json.loads(drive.courses_json or "[]")
    if student.course not in courses:
        fail(422, "This drive is not open to the student's programme")
    config = load_config(db)
    if body.attended:
        review = "none"
    elif body.emergency_claimed:
        review = "pending"
        open_flag(
            db,
            student_id=student.id,
            kind="absence_review",
            message=f"Emergency exception claimed for {drive.title}.",
            drive_id=drive.id,
        )
    else:
        review = "none"
        student.exclusion_drives_remaining = int(config["absence_exclusion_drives"])
    row = Attendance(
        drive_id=drive.id,
        student_id=student.id,
        activity=body.activity,
        attended=body.attended,
        emergency_claimed=body.emergency_claimed,
        review_status=review,
        note=body.note or None,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        user,
        "attendance.record",
        "attendance",
        row.id,
        None,
        {"student_id": student.id, "drive_id": drive.id, "attended": body.attended, "activity": body.activity},
        client_ip(request),
    )
    db.commit()
    return attendance_dict(row, drive.title)


@router.post("/attendance/{attendance_id}/review")
def review_attendance(
    attendance_id: str,
    body: AttendanceReview,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    row = db.get(Attendance, attendance_id)
    if row is None or row.review_status != "pending":
        fail(404, "There is no emergency exception waiting for review")
    student = db.get(Student, row.student_id)
    if student is None:
        fail(404, "Student record not found")
    before = {"review_status": row.review_status, "exclusion_drives_remaining": student.exclusion_drives_remaining}
    row.review_status = body.decision
    if body.decision == "approved":
        student.exclusion_drives_remaining = 0
    else:
        student.exclusion_drives_remaining = int(load_config(db)["absence_exclusion_drives"])
    if body.reason:
        row.note = body.reason.strip()
    audit(
        db,
        user,
        "attendance.review",
        "attendance",
        row.id,
        before,
        {"review_status": row.review_status, "exclusion_drives_remaining": student.exclusion_drives_remaining},
        client_ip(request),
    )
    db.commit()
    drive = db.get(Drive, row.drive_id)
    return attendance_dict(row, drive.title if drive else None)
