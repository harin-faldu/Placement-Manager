from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.database import get_db
from app.core.deps import require
from app.core.http import client_ip, fail
from app.persistence.models import Company, ComplianceFlag, Drive, Offer, PolicyConfig, Student, User
from app.domain.policy import category_for, evaluate, narrative
from app.persistence.schemas import FlagResolve, PolicyCheck, PolicyUpdate
from app.services.placement import audit, can_read_student, drive_snap, load_config, pending_absence_ids, snaps_for, student_snap

router = APIRouter(prefix="/api", tags=["policy"])


@router.get("/policy")
def get_policy(user: User = Depends(require("admin", "officer", "coordinator")), db: Session = Depends(get_db)):
    config = load_config(db)
    return {
        "session": "2026-27",
        "narrative": narrative(config),
        "config": {
            "a_plus_min": config["a_plus_min"],
            "a_min": config["a_min"],
            "b_min": config["b_min"],
            "b_multiplier": config["b_multiplier"],
            "acceptance_hours_cap": config["acceptance_hours_cap"],
            "absence_exclusion_drives": config["absence_exclusion_drives"],
            "a_plus_exits_process": config["a_plus_exits_process"],
            "category_can_override_fte_lock": config["category_can_override_fte_lock"],
            "if_after_f": config["if_after_f"],
        },
        "can_edit": user.role == "admin",
    }


@router.put("/policy")
def update_policy(
    body: PolicyUpdate,
    request: Request,
    user: User = Depends(require("admin")),
    db: Session = Depends(get_db),
):
    if not (body.a_plus_min > body.a_min > body.b_min):
        fail(422, "Category thresholds must descend from A+ to A to B")
    current = load_config(db)
    updated = dict(current)
    updated.update(body.model_dump())
    row = db.get(PolicyConfig, 1)
    before = {key: current[key] for key in body.model_dump()}
    if row is None:
        row = PolicyConfig(id=1, data_json=json.dumps(updated), updated_at=utcnow(), updated_by=user.id)
        db.add(row)
    else:
        row.data_json = json.dumps(updated)
        row.updated_at = utcnow()
        row.updated_by = user.id
    audit(db, user, "policy.update", "policy", "1", before, body.model_dump(), client_ip(request))
    db.commit()
    return {"config": body.model_dump(), "narrative": narrative(updated)}


@router.post("/policy/check")
def check_policy(
    body: PolicyCheck,
    user: User = Depends(require("admin", "officer", "coordinator")),
    db: Session = Depends(get_db),
):
    student = db.get(Student, body.student_id)
    if student is None or not can_read_student(user, student):
        fail(404, "Student record not found")
    drive = db.get(Drive, body.drive_id)
    if drive is None:
        fail(404, "Drive not found")
    pending = student.id in pending_absence_ids(db, [student.id])
    evaluation = evaluate(student_snap(student, pending), snaps_for(db, student), drive_snap(drive), load_config(db))
    return evaluation.as_dict()


@router.get("/compliance")
def list_compliance(
    _user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    config = load_config(db)
    rows = db.scalars(select(ComplianceFlag).order_by(ComplianceFlag.created_at.desc()).limit(40)).all()
    items = []
    for flag in rows:
        student = db.get(Student, flag.student_id)
        if student is None:
            continue
        offer = db.get(Offer, flag.offer_id) if flag.offer_id else None
        company = db.get(Company, offer.company_id) if offer else None
        resolver = db.get(User, flag.resolved_by) if flag.resolved_by else None
        reasons: list[str] = []
        if flag.drive_id:
            drive = db.get(Drive, flag.drive_id)
            if drive is not None:
                pending = student.id in pending_absence_ids(db, [student.id])
                evaluation = evaluate(student_snap(student, pending), snaps_for(db, student), drive_snap(drive), config)
                reasons = [check.detail for check in evaluation.checks if check.status in {"fail", "review"}]
        history = []
        for snap in snaps_for(db, student):
            if snap.voided:
                continue
            history.append(
                {
                    "company": snap.company_name,
                    "offer_type": snap.offer_type,
                    "acceptance_status": snap.acceptance_status,
                    "category": category_for(snap.ctc_lpa, config) if snap.offer_type in {"F", "IF"} else None,
                    "ctc_lpa": snap.ctc_lpa,
                }
            )
        items.append(
            {
                "id": flag.id,
                "kind": flag.kind,
                "message": flag.message,
                "status": flag.status,
                "created_at": flag.created_at.isoformat(timespec="seconds"),
                "student_id": student.id,
                "student_name": student.full_name,
                "placement_id": student.placement_id,
                "offer_company": company.name if company else None,
                "reasons": reasons,
                "history": history,
                "resolution_note": flag.resolution_note,
                "resolved_at": flag.resolved_at.isoformat(timespec="seconds") if flag.resolved_at else None,
                "resolved_by": resolver.email if resolver else None,
            }
        )
    return {"items": items}


@router.post("/compliance/{flag_id}/resolve")
def resolve_flag(
    flag_id: str,
    body: FlagResolve,
    request: Request,
    user: User = Depends(require("admin", "officer")),
    db: Session = Depends(get_db),
):
    flag = db.get(ComplianceFlag, flag_id)
    if flag is None or flag.status != "open":
        fail(404, "Open compliance item not found")
    flag.status = "resolved"
    flag.resolved_at = utcnow()
    flag.resolved_by = user.id
    flag.resolution_note = body.note.strip()
    audit(
        db,
        user,
        "compliance.resolve",
        "compliance",
        flag.id,
        {"status": "open"},
        {"status": "resolved", "note": body.note},
        client_ip(request),
    )
    db.commit()
    return {"id": flag.id, "status": flag.status, "resolved_by": user.email, "resolution_note": flag.resolution_note}
