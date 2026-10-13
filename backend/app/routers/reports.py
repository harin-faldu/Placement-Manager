from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require
from app.domain import course_name
from app.http import client_ip, fail
from app.models import Company, Drive, Student, User
from app.services import audit, classify_drive, collect_report_inputs, drive_dict, expire_due_offers, load_config
from app.stats import summarize

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/overview")
def overview(
    request: Request,
    user: User = Depends(require("admin", "officer", "coordinator", "recruiter")),
    db: Session = Depends(get_db),
):
    expire_due_offers(db, client_ip(request))
    config = load_config(db)
    if user.role == "recruiter":
        company = db.get(Company, user.company_id) if user.company_id else None
        if company is None:
            fail(403, "This recruiter account is not linked to a company")
        drives = db.scalars(select(Drive).where(Drive.company_id == company.id)).all()
        items = []
        for drive in drives:
            allowed, withheld = classify_drive(db, drive, config)
            payload = drive_dict(drive, company.name)
            payload["eligible_count"] = len(allowed)
            payload["withheld_count"] = len(withheld)
            items.append(payload)
        return {
            "scope": "company",
            "company": company.name,
            "session": "2026-27",
            "drives": items,
            "definitions": {
                "eligible": "Students the policy would allow into this drive. Names are shown without contact details or compensation.",
                "withheld": "Students withheld by registration, eligibility, offer-type, or category rules. Their names are not shared.",
            },
        }

    stmt = select(Student).where(Student.archived_at.is_(None))
    if user.role == "coordinator":
        stmt = stmt.where(Student.course == user.course)
    students = list(db.scalars(stmt).all())
    snaps, offers, flags = collect_report_inputs(db, students)
    report = summarize(snaps, offers, flags, config)
    report["scope"] = "course" if user.role == "coordinator" else "university"
    report["course"] = user.course
    report["course_name"] = course_name(user.course) if user.course else None
    report["session"] = "2026-27"
    audit(db, user, "report.view", "report", report["scope"], None, {"students": len(students)}, client_ip(request))
    db.commit()
    return report
