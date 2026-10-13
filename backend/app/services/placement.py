from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.audit import write_audit
from app.core.clock import utcnow
from app.domain.catalog import (
    DEFAULT_CONFIG,
    ELIGIBILITY_LABELS,
    OFFER_LABELS,
    PLACEMENT_LABELS,
    REGISTRATION_LABELS,
    ROLE_LABELS,
    DriveSnap,
    FlagSnap,
    OfferSnap,
    StudentSnap,
    course_name,
    course_short,
)
from app.persistence.models import (
    Attendance,
    AuditLog,
    Company,
    ComplianceFlag,
    Drive,
    Offer,
    OfferEvent,
    PolicyConfig,
    Student,
    User,
)
from app.domain.policy import category_for, evaluate, placement_status_of, standing
from app.core.security import decrypt_mobile, mask_mobile
from app.domain.validate import round_money


def load_config(db: Session) -> dict:
    row = db.get(PolicyConfig, 1)
    config = dict(DEFAULT_CONFIG)
    if row:
        stored = json.loads(row.data_json)
        for key in DEFAULT_CONFIG:
            if key in stored:
                config[key] = stored[key]
    return config


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict | None,
    after: dict | None,
    ip: str | None,
) -> None:
    write_audit(
        db,
        actor_id=user.id if user else None,
        actor_email=user.email if user else "system",
        actor_role=user.role if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        ip=ip,
    )


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "course": user.course,
        "course_name": course_name(user.course) if user.course else None,
        "company_id": user.company_id,
        "student_id": user.student_id,
        "mfa_enabled": user.mfa_enabled,
        "is_active": user.is_active,
    }


def can_read_student(user: User, student: Student) -> bool:
    if user.role in {"admin", "officer"}:
        return True
    if user.role == "coordinator":
        return user.course == student.course
    if user.role == "student":
        return user.student_id == student.id
    return False


def can_see_contact(user: User, student: Student) -> bool:
    return can_read_student(user, student)


def can_see_compensation(user: User, student: Student) -> bool:
    return can_read_student(user, student)


def coordinator_field_error(user: User, payload: dict) -> str | None:
    if user.role != "coordinator":
        return None
    allowed = {"mobile", "email", "cgpa", "remarks"}
    blocked = [field for field, value in payload.items() if value is not None and field not in allowed]
    if blocked:
        return "Course coordinators cannot change registration, eligibility, programme, or placement fields"
    return None


def student_snap(student: Student, pending_absence: bool = False) -> StudentSnap:
    if student.exclusion_drives_remaining > 0:
        review = "excluded"
    elif pending_absence:
        review = "pending"
    else:
        review = "clear"
    return StudentSnap(
        id=student.id,
        placement_id=student.placement_id,
        full_name=student.full_name,
        course=student.course,
        batch=student.batch,
        registration_status=student.registration_status,
        eligibility_status=student.eligibility_status,
        cgpa=student.cgpa,
        exclusion_drives_remaining=student.exclusion_drives_remaining,
        absence_review=review,
        archived=student.archived_at is not None,
    )


def offer_snap(offer: Offer, company_name: str) -> OfferSnap:
    return OfferSnap(
        id=offer.id,
        student_id=offer.student_id,
        company_id=offer.company_id,
        company_name=company_name,
        offer_type=offer.offer_type,
        ctc_lpa=offer.ctc_lpa,
        stipend_amount=offer.stipend_amount,
        stipend_period=offer.stipend_period,
        acceptance_status=offer.acceptance_status,
        joining_status=offer.joining_status,
        ppo_status=offer.ppo_status,
        voided=offer.voided,
        is_off_campus=offer.is_off_campus,
    )


def drive_snap(drive: Drive) -> DriveSnap:
    return DriveSnap(
        company_id=drive.company_id,
        offer_type=drive.offer_type,
        ctc_lpa=drive.ctc_lpa,
        courses=json.loads(drive.courses_json or "[]"),
        min_cgpa=drive.min_cgpa,
        company_hours=drive.acceptance_hours,
    )


def offers_for(db: Session, student_id: str) -> list[Offer]:
    return list(db.scalars(select(Offer).where(Offer.student_id == student_id).order_by(Offer.offer_date, Offer.created_at)))


def company_map(db: Session, offers: list[Offer]) -> dict[str, str]:
    ids = {offer.company_id for offer in offers}
    if not ids:
        return {}
    rows = db.scalars(select(Company).where(Company.id.in_(ids))).all()
    return {row.id: row.name for row in rows}


def snaps_for(db: Session, student: Student) -> list[OfferSnap]:
    rows = offers_for(db, student.id)
    names = company_map(db, rows)
    return [offer_snap(row, names.get(row.company_id, "")) for row in rows]


def pending_absence_ids(db: Session, student_ids: list[str] | None = None) -> set[str]:
    stmt = select(Attendance.student_id).where(Attendance.review_status == "pending")
    if student_ids is not None:
        if not student_ids:
            return set()
        stmt = stmt.where(Attendance.student_id.in_(student_ids))
    return set(db.scalars(stmt).all())


def refresh_status(db: Session, student: Student) -> None:
    student.placement_status = placement_status_of(snaps_for(db, student))
    student.updated_at = utcnow()


def student_dict(student: Student, user: User) -> dict:
    show_contact = can_see_contact(user, student)
    mobile = decrypt_mobile(student.mobile_encrypted) if show_contact else None
    return {
        "id": student.id,
        "placement_id": student.placement_id,
        "full_name": student.full_name,
        "email": student.email if show_contact else None,
        "mobile": mobile,
        "course": student.course,
        "course_name": course_name(student.course),
        "course_short": course_short(student.course),
        "batch": student.batch,
        "registration_status": student.registration_status,
        "registration_label": REGISTRATION_LABELS.get(student.registration_status, student.registration_status),
        "eligibility_status": student.eligibility_status,
        "eligibility_label": ELIGIBILITY_LABELS.get(student.eligibility_status, student.eligibility_status),
        "placement_status": student.placement_status,
        "placement_status_label": PLACEMENT_LABELS.get(student.placement_status, student.placement_status),
        "cgpa": student.cgpa,
        "remarks": student.remarks if can_read_student(user, student) else None,
        "exclusion_drives_remaining": student.exclusion_drives_remaining,
        "archived": student.archived_at is not None,
        "updated_at": student.updated_at.isoformat(timespec="seconds"),
    }


def offer_dict(offer: Offer, company_name: str, *, reveal_pay: bool) -> dict:
    return {
        "id": offer.id,
        "student_id": offer.student_id,
        "company_id": offer.company_id,
        "company_name": company_name,
        "drive_id": offer.drive_id,
        "offer_type": offer.offer_type,
        "offer_type_label": OFFER_LABELS.get(offer.offer_type, offer.offer_type),
        "category": offer.category if reveal_pay else None,
        "ctc_lpa": offer.ctc_lpa if reveal_pay else None,
        "stipend_amount": offer.stipend_amount if reveal_pay else None,
        "stipend_period": offer.stipend_period if reveal_pay else None,
        "ppo_status": offer.ppo_status,
        "acceptance_status": offer.acceptance_status,
        "joining_status": offer.joining_status,
        "offer_date": offer.offer_date.isoformat(),
        "acceptance_deadline": offer.acceptance_deadline.isoformat(timespec="seconds") if offer.acceptance_deadline else None,
        "acceptance_hours": offer.acceptance_hours,
        "is_off_campus": offer.is_off_campus,
        "noc_status": offer.noc_status,
        "voided": offer.voided,
        "void_reason": offer.void_reason,
        "policy_verdict": offer.policy_verdict,
        "override_reason": offer.override_reason if reveal_pay else None,
        "remarks": offer.remarks,
    }


def drive_dict(drive: Drive, company_name: str) -> dict:
    return {
        "id": drive.id,
        "company_id": drive.company_id,
        "company_name": company_name,
        "title": drive.title,
        "offer_type": drive.offer_type,
        "offer_type_label": OFFER_LABELS.get(drive.offer_type, drive.offer_type),
        "ctc_lpa": drive.ctc_lpa,
        "stipend_amount": drive.stipend_amount,
        "stipend_period": drive.stipend_period,
        "acceptance_hours": drive.acceptance_hours,
        "courses": json.loads(drive.courses_json or "[]"),
        "min_cgpa": drive.min_cgpa,
        "scheduled_on": drive.scheduled_on.isoformat() if drive.scheduled_on else None,
        "notes": drive.notes,
    }


def attendance_dict(row: Attendance, drive_title: str | None = None) -> dict:
    return {
        "id": row.id,
        "drive_id": row.drive_id,
        "drive_title": drive_title,
        "student_id": row.student_id,
        "activity": row.activity,
        "attended": row.attended,
        "emergency_claimed": row.emergency_claimed,
        "review_status": row.review_status,
        "note": row.note,
        "created_at": row.created_at.isoformat(timespec="seconds"),
    }


def profile_snapshot(student: Student, *, reveal_contact: bool) -> dict:
    mobile = decrypt_mobile(student.mobile_encrypted) if reveal_contact else None
    return {
        "placement_id": student.placement_id,
        "full_name": student.full_name,
        "email": student.email if reveal_contact else None,
        "mobile": mask_mobile(mobile) if reveal_contact else None,
        "course": student.course,
        "batch": student.batch,
        "registration_status": student.registration_status,
        "eligibility_status": student.eligibility_status,
        "placement_status": student.placement_status,
        "cgpa": student.cgpa,
        "exclusion_drives_remaining": student.exclusion_drives_remaining,
        "remarks": student.remarks,
        "archived": student.archived_at is not None,
    }


def offer_snapshot(offer: Offer) -> dict:
    return {
        "offer_type": offer.offer_type,
        "category": offer.category,
        "ctc_lpa": offer.ctc_lpa,
        "stipend_amount": offer.stipend_amount,
        "acceptance_status": offer.acceptance_status,
        "joining_status": offer.joining_status,
        "ppo_status": offer.ppo_status,
        "noc_status": offer.noc_status,
        "voided": offer.voided,
        "is_off_campus": offer.is_off_campus,
    }


def validate_package(offer_type: str, ctc: float | None, stipend: float | None, period: str | None) -> None:
    from app.core.http import fail

    if offer_type == "I":
        if stipend is None or stipend < 0:
            fail(422, "An internship-only offer needs a stipend")
        if ctc is not None:
            fail(422, "An internship-only offer records a stipend, not annual CTC")
        if period not in {"monthly", "total"}:
            fail(422, "Record whether the stipend is monthly or a total")
    elif offer_type == "F":
        if ctc is None or ctc <= 0:
            fail(422, "An FTE offer needs an annual CTC in LPA")
        if stipend is not None:
            fail(422, "An FTE-only offer does not record an internship stipend")
    elif offer_type == "IF":
        if ctc is None or ctc <= 0 or stipend is None or stipend < 0:
            fail(422, "Internship + PPO/FTE needs both a stipend and an annual CTC")
        if period not in {"monthly", "total"}:
            fail(422, "Record whether the stipend is monthly or a total")
    else:
        fail(422, "Offer type must be I, F, or I+F")
    if ctc is not None and (ctc <= 0 or ctc > 200):
        fail(422, "CTC must be between 0 and 200 LPA")
    if stipend is not None and stipend > 10_000_000:
        fail(422, "Stipend is outside the accepted range")


def apply_category(offer: Offer, config: dict) -> None:
    offer.ctc_lpa = round_money(offer.ctc_lpa)
    offer.stipend_amount = round_money(offer.stipend_amount)
    offer.category = category_for(offer.ctc_lpa, config) if offer.offer_type in {"F", "IF"} else None


def open_flag(
    db: Session,
    *,
    student_id: str,
    kind: str,
    message: str,
    offer_id: str | None = None,
    drive_id: str | None = None,
) -> None:
    existing = db.scalar(
        select(ComplianceFlag).where(
            ComplianceFlag.student_id == student_id,
            ComplianceFlag.kind == kind,
            ComplianceFlag.status == "open",
            ComplianceFlag.offer_id == offer_id,
            ComplianceFlag.message == message,
        )
    )
    if existing:
        return
    db.add(
        ComplianceFlag(
            student_id=student_id,
            offer_id=offer_id,
            drive_id=drive_id,
            kind=kind,
            message=message,
            status="open",
        )
    )


def expire_due_offers(db: Session, ip: str | None = None) -> int:
    now = utcnow()
    rows = db.scalars(
        select(Offer).where(
            Offer.acceptance_status == "pending",
            Offer.voided.is_(False),
            Offer.acceptance_deadline.is_not(None),
            Offer.acceptance_deadline < now,
        )
    ).all()
    if not rows:
        return 0
    seen: set[str] = set()
    for offer in rows:
        before = offer_snapshot(offer)
        offer.acceptance_status = "expired"
        offer.updated_at = now
        db.add(
            OfferEvent(
                offer_id=offer.id,
                action="expired",
                before_json=json.dumps(before),
                after_json=json.dumps(offer_snapshot(offer)),
                actor_id=None,
            )
        )
        audit(db, None, "offer.expire", "offer", offer.id, before, offer_snapshot(offer), ip)
        open_flag(
            db,
            student_id=offer.student_id,
            kind="offer_expired",
            message="An offer passed its acceptance deadline and was marked expired.",
            offer_id=offer.id,
        )
        seen.add(offer.student_id)
    for student_id in seen:
        student = db.get(Student, student_id)
        if student:
            refresh_status(db, student)
    db.commit()
    return len(rows)


def standing_for(db: Session, student: Student) -> dict:
    pending = student.id in pending_absence_ids(db, [student.id])
    return standing(student_snap(student, pending), snaps_for(db, student), load_config(db))


def collect_report_inputs(db: Session, students: list[Student]) -> tuple[list[StudentSnap], list[OfferSnap], list[FlagSnap]]:
    ids = [student.id for student in students]
    pending = pending_absence_ids(db, ids)
    snaps = [student_snap(student, student.id in pending) for student in students]
    if not ids:
        return snaps, [], []
    offer_rows = db.scalars(select(Offer).where(Offer.student_id.in_(ids))).all()
    names = company_map(db, list(offer_rows))
    offer_snaps = [offer_snap(row, names.get(row.company_id, "")) for row in offer_rows]
    flag_rows = db.scalars(
        select(ComplianceFlag).where(ComplianceFlag.student_id.in_(ids), ComplianceFlag.status == "open")
    ).all()
    flags = [FlagSnap(row.student_id, row.kind, row.message) for row in flag_rows]
    return snaps, offer_snaps, flags


def explain_drive(db: Session, drive: Drive, config: dict, course: str | None = None) -> list[dict]:
    courses = json.loads(drive.courses_json or "[]")
    if course:
        courses = [item for item in courses if item == course]
    if not courses:
        return []
    students = list(
        db.scalars(
            select(Student)
            .where(Student.archived_at.is_(None), Student.course.in_(courses))
            .order_by(Student.full_name)
        ).all()
    )
    pending = pending_absence_ids(db, [student.id for student in students])
    snap = drive_snap(drive)
    explained = []
    for student in students:
        evaluation = evaluate(student_snap(student, student.id in pending), snaps_for(db, student), snap, config)
        reasons = [check.detail for check in evaluation.checks if check.status in {"fail", "review"}]
        if evaluation.verdict == "allow":
            reasons = ["Registration, eligibility, offer type, and category rules all pass."]
        explained.append(
            {
                "id": student.id,
                "placement_id": student.placement_id,
                "full_name": student.full_name,
                "course_short": course_short(student.course),
                "batch": student.batch,
                "verdict": evaluation.verdict,
                "reasons": reasons,
            }
        )
    order = {"block": 0, "review": 1, "allow": 2}
    explained.sort(key=lambda item: (order.get(item["verdict"], 9), item["full_name"]))
    return explained


def classify_drive(db: Session, drive: Drive, config: dict) -> tuple[list[Student], list[Student]]:
    courses = json.loads(drive.courses_json or "[]")
    if not courses:
        return [], []
    students = list(
        db.scalars(select(Student).where(Student.archived_at.is_(None), Student.course.in_(courses))).all()
    )
    pending = pending_absence_ids(db, [student.id for student in students])
    allowed: list[Student] = []
    withheld: list[Student] = []
    snap = drive_snap(drive)
    for student in students:
        verdict = evaluate(student_snap(student, student.id in pending), snaps_for(db, student), snap, config).verdict
        if verdict == "allow":
            allowed.append(student)
        else:
            withheld.append(student)
    return allowed, withheld


def public_audit(row: AuditLog) -> dict:
    payload = json.loads(row.payload)
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(timespec="seconds"),
        "ip": row.ip,
        "action": payload.get("action"),
        "actor_email": payload.get("actor_email"),
        "actor_role": payload.get("actor_role"),
        "entity_type": payload.get("entity_type"),
        "entity_id": payload.get("entity_id"),
        "before": payload.get("before"),
        "after": payload.get("after"),
    }
