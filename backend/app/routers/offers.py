from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import today_ist, utcnow
from app.database import get_db
from app.deps import require
from app.domain import DriveSnap
from app.http import client_ip, fail
from app.models import Company, Drive, Offer, OfferEvent, Student, User
from app.policy import acceptance_window, evaluate
from app.schemas import OfferCreate, OfferPatch, OfferVoid
from app.services import (
    audit,
    can_read_student,
    company_map,
    drive_snap,
    load_config,
    offer_dict,
    offer_snapshot,
    open_flag,
    pending_absence_ids,
    refresh_status,
    snaps_for,
    student_snap,
    validate_package,
    apply_category,
)

router = APIRouter(prefix="/api/offers", tags=["offers"])


def _event(db: Session, offer: Offer, action: str, before: dict | None, actor_id: str | None) -> None:
    db.add(
        OfferEvent(
            offer_id=offer.id,
            action=action,
            before_json=json.dumps(before) if before is not None else None,
            after_json=json.dumps(offer_snapshot(offer)),
            actor_id=actor_id,
        )
    )


def _gate(db: Session, user: User, student: Student, snap: DriveSnap, *, override_reason: str | None) -> dict:
    config = load_config(db)
    pending = student.id in pending_absence_ids(db, [student.id])
    evaluation = evaluate(student_snap(student, pending), snaps_for(db, student), snap, config)
    if evaluation.verdict == "block":
        if user.role == "admin" and override_reason and len(override_reason.strip()) >= 8:
            return evaluation.as_dict() | {"override": True}
        fail(409, "Policy blocked this offer", evaluation=evaluation.as_dict())
    return evaluation.as_dict() | {"override": False}


@router.post("")
def create_offer(
    body: OfferCreate,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    student = db.get(Student, body.student_id)
    if student is None or student.archived_at is not None:
        fail(404, "Student record not found")
    if body.offer_date > today_ist() or body.offer_date < today_ist() - timedelta(days=800):
        fail(422, "Offer date must be today or a recent past date")

    if body.drive_id:
        drive = db.get(Drive, body.drive_id)
        if drive is None:
            fail(404, "Drive not found")
        company_id = drive.company_id
        offer_type = drive.offer_type
        ctc = drive.ctc_lpa
        stipend = drive.stipend_amount
        period = drive.stipend_period
        hours = drive.acceptance_hours
        off_campus = False
        snap = drive_snap(drive)
    else:
        if not body.company_id or not body.offer_type:
            fail(422, "An offer without a drive needs a company and an offer type")
        company = db.get(Company, body.company_id)
        if company is None:
            fail(404, "Company not found")
        company_id = company.id
        offer_type = body.offer_type
        ctc = body.ctc_lpa
        stipend = body.stipend_amount
        period = body.stipend_period
        hours = body.acceptance_hours
        off_campus = body.is_off_campus
        snap = DriveSnap(company_id, offer_type, ctc, [student.course], None, hours)

    validate_package(offer_type, ctc, stipend, period)
    if body.acceptance_status == "accepted":
        decision = _gate(db, user, student, snap, override_reason=body.override_reason)
    else:
        decision = _gate(db, user, student, snap, override_reason=body.override_reason)

    config = load_config(db)
    deadline, window = acceptance_window(body.offer_date, hours, int(config["acceptance_hours_cap"]))
    ppo = body.ppo_status
    if ppo is None:
        ppo = "pending" if offer_type == "IF" else "na"
    offer = Offer(
        student_id=student.id,
        company_id=company_id,
        drive_id=body.drive_id,
        offer_type=offer_type,
        ctc_lpa=ctc,
        stipend_amount=stipend,
        stipend_period=period,
        ppo_status=ppo,
        acceptance_status=body.acceptance_status,
        joining_status=body.joining_status,
        offer_date=body.offer_date,
        acceptance_deadline=deadline,
        acceptance_hours=window,
        is_off_campus=off_campus,
        noc_status=body.noc_status if off_campus else body.noc_status,
        remarks=body.remarks or None,
        created_by=user.id,
        policy_verdict="override" if decision.get("override") else decision["verdict"],
        override_reason=body.override_reason if decision.get("override") else None,
    )
    apply_category(offer, config)
    db.add(offer)
    db.flush()
    _event(db, offer, "created", None, user.id)
    if decision["verdict"] == "review":
        open_flag(
            db,
            student_id=student.id,
            kind="policy_review",
            message="An offer was recorded and referred for policy review.",
            offer_id=offer.id,
            drive_id=body.drive_id,
        )
    if decision.get("override"):
        open_flag(
            db,
            student_id=student.id,
            kind="policy_override",
            message="An administrator recorded an offer against a policy block.",
            offer_id=offer.id,
            drive_id=body.drive_id,
        )
    refresh_status(db, student)
    names = company_map(db, [offer])
    audit(db, user, "offer.create", "offer", offer.id, None, offer_snapshot(offer), client_ip(request))
    db.commit()
    return {"offer": offer_dict(offer, names.get(offer.company_id, ""), reveal_pay=True), "evaluation": decision}


@router.patch("/{offer_id}")
def update_offer(
    offer_id: str,
    body: OfferPatch,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if offer is None or offer.voided:
        fail(404, "Offer not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        fail(400, "No changes were provided")
    student = db.get(Student, offer.student_id)
    if student is None:
        fail(404, "Student record not found")
    before = offer_snapshot(offer)
    becoming_accepted = changes.get("acceptance_status") == "accepted" and offer.acceptance_status != "accepted"
    if becoming_accepted:
        if offer.drive_id:
            drive = db.get(Drive, offer.drive_id)
            snap = drive_snap(drive) if drive else DriveSnap(offer.company_id, offer.offer_type, offer.ctc_lpa, [student.course], None, offer.acceptance_hours)
        else:
            snap = DriveSnap(offer.company_id, offer.offer_type, offer.ctc_lpa, [student.course], None, offer.acceptance_hours)
        others = [item for item in snaps_for(db, student) if item.id != offer.id]
        config = load_config(db)
        pending = student.id in pending_absence_ids(db, [student.id])
        evaluation = evaluate(student_snap(student, pending), others, snap, config)
        if evaluation.verdict == "block" and not (user.role == "admin" and body.override_reason and len(body.override_reason.strip()) >= 8):
            fail(409, "Policy blocked acceptance of this offer", evaluation=evaluation.as_dict())
        if evaluation.verdict == "block":
            offer.policy_verdict = "override"
            offer.override_reason = body.override_reason
            open_flag(db, student_id=student.id, kind="policy_override", message="Acceptance was recorded against a policy block.", offer_id=offer.id)
        elif evaluation.verdict == "review":
            offer.policy_verdict = "review"
            open_flag(db, student_id=student.id, kind="policy_review", message="Acceptance was referred for policy review.", offer_id=offer.id)
        else:
            offer.policy_verdict = "allow"
    if "acceptance_status" in changes and changes["acceptance_status"]:
        if offer.acceptance_status == "expired" and user.role != "admin":
            fail(403, "Only a Placement Administrator can reopen an expired offer")
        offer.acceptance_status = changes["acceptance_status"]
    if "joining_status" in changes and changes["joining_status"]:
        offer.joining_status = changes["joining_status"]
    if "ppo_status" in changes and changes["ppo_status"]:
        offer.ppo_status = changes["ppo_status"]
    if "noc_status" in changes and changes["noc_status"]:
        offer.noc_status = changes["noc_status"]
    if "remarks" in changes:
        offer.remarks = changes["remarks"] or None
    offer.updated_at = utcnow()
    _event(db, offer, "updated", before, user.id)
    refresh_status(db, student)
    audit(db, user, "offer.update", "offer", offer.id, before, offer_snapshot(offer), client_ip(request))
    db.commit()
    company = db.get(Company, offer.company_id)
    return offer_dict(offer, company.name if company else "", reveal_pay=True)


@router.post("/{offer_id}/void")
def void_offer(
    offer_id: str,
    body: OfferVoid,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if offer is None or offer.voided:
        fail(404, "Offer not found")
    student = db.get(Student, offer.student_id)
    if student is None or not can_read_student(user, student):
        fail(404, "Offer not found")
    before = offer_snapshot(offer)
    offer.voided = True
    offer.void_reason = body.reason.strip()
    offer.updated_at = utcnow()
    _event(db, offer, "voided", before, user.id)
    refresh_status(db, student)
    audit(db, user, "offer.void", "offer", offer.id, before, offer_snapshot(offer), client_ip(request))
    db.commit()
    company = db.get(Company, offer.company_id)
    return offer_dict(offer, company.name if company else "", reveal_pay=True)


@router.get("/{offer_id}/history")
def offer_history(
    offer_id: str,
    user: User = Depends(require("admin", "officer", "coordinator", "student")),
    db: Session = Depends(get_db),
):
    offer = db.get(Offer, offer_id)
    if offer is None:
        fail(404, "Offer not found")
    student = db.get(Student, offer.student_id)
    if student is None or not can_read_student(user, student):
        fail(404, "Offer not found")
    events = db.scalars(select(OfferEvent).where(OfferEvent.offer_id == offer.id).order_by(OfferEvent.created_at)).all()
    return {
        "events": [
            {
                "id": event.id,
                "action": event.action,
                "before": json.loads(event.before_json) if event.before_json else None,
                "after": json.loads(event.after_json) if event.after_json else None,
                "created_at": event.created_at.isoformat(timespec="seconds"),
            }
            for event in events
        ]
    }
