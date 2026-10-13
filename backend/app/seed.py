from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.clock import today_ist, utcnow
from app.domain import COURSES, DEFAULT_CONFIG
from app.models import Attendance, Company, ComplianceFlag, Drive, Offer, PolicyConfig, Student, User
from app.policy import acceptance_window, placement_status_of
from app.security import encrypt_mobile, hash_password, mobile_digest
from app.services import offer_snap
from app.validate import clean_mobile

ALL_COURSES = [course["code"] for course in COURSES]


def seed(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(User)):
        return

    db.add(PolicyConfig(id=1, data_json=json.dumps(DEFAULT_CONFIG), updated_at=utcnow()))
    companies = {
        name: Company(name=name)
        for name in [
            "Northstar Labs",
            "Helios Analytics",
            "Kavach Security",
            "Bluepeak Systems",
            "Fieldnote Technologies",
            "Meridian Forensics",
        ]
    }
    db.add_all(companies.values())
    db.flush()

    drive_rows = [
        ("Northstar A+ FTE", "Northstar Labs", "F", 18, None, None, 24, 7.0),
        ("Northstar Internship + PPO", "Northstar Labs", "IF", 22, 40000, "monthly", 12, 8.0),
        ("Helios FTE", "Helios Analytics", "F", 12, None, None, 24, 7.0),
        ("Helios Associate", "Helios Analytics", "F", 11, None, None, 48, 6.5),
        ("Kavach Summer Internship", "Kavach Security", "I", None, 25000, "monthly", 24, 7.0),
        ("Kavach FTE 2026", "Kavach Security", "F", 14, None, None, 24, 7.0),
        ("Bluepeak FTE", "Bluepeak Systems", "F", 8, None, None, 24, None),
        ("Fieldnote FTE", "Fieldnote Technologies", "F", 4.5, None, None, 24, None),
        ("Fieldnote Internship", "Fieldnote Technologies", "I", None, 15000, "monthly", 24, None),
        ("Meridian FTE", "Meridian Forensics", "F", 11, None, None, 24, 7.0),
        ("Meridian Analyst", "Meridian Forensics", "F", 5.5, None, None, 24, None),
    ]
    drives: dict[str, Drive] = {}
    today = today_ist()
    for title, company, offer_type, ctc, stipend, period, hours, cutoff in drive_rows:
        drive = Drive(
            company_id=companies[company].id,
            title=title,
            offer_type=offer_type,
            ctc_lpa=ctc,
            stipend_amount=stipend,
            stipend_period=period,
            acceptance_hours=hours,
            courses_json=json.dumps(ALL_COURSES),
            min_cgpa=cutoff,
            scheduled_on=today - timedelta(days=21),
        )
        db.add(drive)
        drives[title] = drive
    db.flush()

    people = [
        ("NFSU-2026-001", "Aisha Rahman", "9010000001", "aisha.rahman@nfsu.ac.in", "MTECH_CS", "2026", "registered", "eligible", 9.1, "", 0, False),
        ("NFSU-2026-002", "Rohan Mehta", "9010000002", "rohan.mehta@nfsu.ac.in", "MTECH_CS", "2026", "registered", "eligible", 8.6, "", 0, False),
        ("NFSU-2026-003", "Neel Kapoor", "9010000003", "neel.kapoor@nfsu.ac.in", "MTECH_AIDS", "2026", "registered", "eligible", 8.1, "", 0, False),
        ("NFSU-2025-004", "Sara Iqbal", "9010000004", "sara.iqbal@nfsu.ac.in", "MTECH_AIDS", "2025", "registered", "eligible", 7.8, "Off-campus offer. NOC issued.", 0, False),
        ("NFSU-2026-005", "Vikram Desai", "9010000005", "vikram.desai@nfsu.ac.in", "BTECH_MTECH_CSE", "2026", "registered", "eligible", 9.4, "", 0, False),
        ("NFSU-2026-006", "Meera Nair", "9010000006", "meera.nair@nfsu.ac.in", "MSC_CS", "2026", "registered", "eligible", 8.0, "", 0, False),
        ("NFSU-2026-007", "Ananya Shah", "9010000007", "ananya.shah@nfsu.ac.in", "MTECH_CS", "2026", "registered", "eligible", 8.4, "", 0, False),
        ("NFSU-2026-008", "Kabir Joshi", "9010000008", "kabir.joshi@nfsu.ac.in", "MSC_DFIS", "2026", "registered", "eligible", 7.6, "", 0, False),
        ("NFSU-2025-009", "Tara Menon", "9010000009", "tara.menon@nfsu.ac.in", "MSC_DFIS", "2025", "registered", "pending_verification", 7.2, "Marksheets awaited.", 0, False),
        ("NFSU-2026-010", "Dev Patel", "9010000010", "dev.patel@nfsu.ac.in", "BTECH_MTECH_CSE", "2026", "registered", "ineligible", 6.1, "Academic eligibility not met.", 0, False),
        ("NFSU-2025-011", "Ishaan Rao", "9010000011", "ishaan.rao@nfsu.ac.in", "MTECH_CS", "2025", "deregistered", "eligible", 8.0, "Deregistered on student request.", 0, False),
        ("NFSU-2026-012", "Pia Kulkarni", "9010000012", "pia.kulkarni@nfsu.ac.in", "MTECH_AIDS", "2026", "registered", "eligible", 8.2, "Missed the Kavach pre-placement talk.", 3, False),
        ("NFSU-2026-013", "Arjun Bose", "9010000013", "arjun.bose@nfsu.ac.in", "MSC_CS", "2026", "registered", "eligible", 7.9, "", 0, False),
        ("NFSU-2025-014", "Leela Krishnan", "9010000014", "leela.krishnan@nfsu.ac.in", "BTECH_MTECH_CSE", "2025", "registered", "eligible", 7.5, "", 0, False),
        ("NFSU-2026-015", "Harsh Vardhan", "9010000015", "harsh.vardhan@nfsu.ac.in", "MSC_DFIS", "2026", "registered", "eligible", 8.3, "", 0, False),
        ("NFSU-2026-016", "Nisha Agarwal", "9010000016", "nisha.agarwal@nfsu.ac.in", "MTECH_CS", "2026", "not_registered", "pending_verification", 7.0, "", 0, False),
        ("NFSU-2025-017", "Omar Farooq", "9010000017", "omar.farooq@nfsu.ac.in", "MTECH_AIDS", "2025", "registered", "eligible", 8.7, "", 0, False),
        ("NFSU-2025-018", "Sana Qureshi", "9010000018", "sana.qureshi@nfsu.ac.in", "MSC_CS", "2025", "registered", "eligible", 8.0, "Archived duplicate entry.", 0, True),
    ]
    students: dict[str, Student] = {}
    for pid, name, mobile, email, course, batch, registration, eligibility, cgpa, remarks, exclusion, archived in people:
        number = clean_mobile(mobile)
        student = Student(
            placement_id=pid,
            full_name=name,
            email=email,
            mobile_encrypted=encrypt_mobile(number),
            mobile_hash=mobile_digest(number),
            course=course,
            batch=batch,
            registration_status=registration,
            eligibility_status=eligibility,
            cgpa=cgpa,
            remarks=remarks or None,
            exclusion_drives_remaining=exclusion,
            archived_at=utcnow() if archived else None,
        )
        db.add(student)
        students[pid] = student
    db.flush()

    officer = User(
        email="officer@nfsu.ac.in",
        password_hash=hash_password("Officer@2026!"),
        full_name="Rahul Banerjee",
        role="officer",
    )
    admin = User(
        email="admin@nfsu.ac.in",
        password_hash=hash_password("Admin@2026!"),
        full_name="Aditi Sharma",
        role="admin",
    )
    coordinator = User(
        email="coord.cs@nfsu.ac.in",
        password_hash=hash_password("Coord@2026!"),
        full_name="Kavita Rao",
        role="coordinator",
        course="MTECH_CS",
    )
    recruiter = User(
        email="recruiter@kavach.example",
        password_hash=hash_password("Recruit@2026!"),
        full_name="Neha Kulkarni",
        role="recruiter",
        company_id=companies["Kavach Security"].id,
    )
    student_user = User(
        email="ananya.shah@nfsu.ac.in",
        password_hash=hash_password("Student@2026!"),
        full_name="Ananya Shah",
        role="student",
        student_id=students["NFSU-2026-007"].id,
    )
    db.add_all([admin, officer, coordinator, recruiter, student_user])
    db.flush()

    offer_rows = [
        ("NFSU-2026-001", "Northstar A+ FTE", "accepted", "joined", "na", False, "not_required", today - timedelta(days=30)),
        ("NFSU-2026-002", "Helios FTE", "accepted", "joined", "na", False, "not_required", today - timedelta(days=25)),
        ("NFSU-2026-003", "Bluepeak FTE", "accepted", "pending", "na", False, "not_required", today - timedelta(days=15)),
        ("NFSU-2025-004", "Fieldnote FTE", "accepted", "joined", "na", True, "issued", today - timedelta(days=40)),
        ("NFSU-2026-005", "Northstar Internship + PPO", "accepted", "pending", "accepted", False, "not_required", today - timedelta(days=12)),
        ("NFSU-2026-006", "Kavach Summer Internship", "accepted", "pending", "na", False, "not_required", today - timedelta(days=8)),
        ("NFSU-2026-013", "Helios Associate", "pending", "pending", "na", False, "not_required", today),
        ("NFSU-2025-014", "Meridian Analyst", "expired", "not_joined", "na", False, "not_required", today - timedelta(days=10)),
        ("NFSU-2026-015", "Fieldnote Internship", "accepted", "pending", "na", False, "not_required", today - timedelta(days=6)),
        ("NFSU-2025-017", "Meridian FTE", "accepted", "joined", "na", False, "not_required", today - timedelta(days=18)),
    ]
    for pid, title, acceptance, joining, ppo, off_campus, noc, offer_date in offer_rows:
        drive = drives[title]
        deadline, window = acceptance_window(offer_date, drive.acceptance_hours, DEFAULT_CONFIG["acceptance_hours_cap"])
        category = None
        if drive.offer_type in {"F", "IF"} and drive.ctc_lpa is not None:
            if drive.ctc_lpa >= 16:
                category = "A+"
            elif drive.ctc_lpa >= 10:
                category = "A"
            elif drive.ctc_lpa >= 6:
                category = "B"
            else:
                category = "C"
        db.add(
            Offer(
                student_id=students[pid].id,
                company_id=drive.company_id,
                drive_id=drive.id,
                offer_type=drive.offer_type,
                category=category,
                ctc_lpa=drive.ctc_lpa,
                stipend_amount=drive.stipend_amount,
                stipend_period=drive.stipend_period,
                ppo_status=ppo,
                acceptance_status=acceptance,
                joining_status=joining,
                offer_date=offer_date,
                acceptance_deadline=deadline,
                acceptance_hours=window,
                is_off_campus=off_campus,
                noc_status=noc,
                policy_verdict="allow",
                created_by=officer.id,
            )
        )
    db.flush()

    for student in students.values():
        rows = db.scalars(select(Offer).where(Offer.student_id == student.id)).all()
        names = {drive.company_id: company.name for company in companies.values() for drive in drives.values() if drive.company_id == company.id}
        student.placement_status = placement_status_of(
            [offer_snap(row, names.get(row.company_id, "")) for row in rows]
        )

    db.add(
        Attendance(
            drive_id=drives["Kavach Summer Internship"].id,
            student_id=students["NFSU-2026-012"].id,
            activity="ppt",
            attended=False,
            emergency_claimed=False,
            review_status="none",
            note="No emergency exception was claimed.",
            created_by=officer.id,
        )
    )
    leela_offer = db.scalar(select(Offer).where(Offer.student_id == students["NFSU-2025-014"].id))
    db.add(
        ComplianceFlag(
            student_id=students["NFSU-2025-014"].id,
            offer_id=leela_offer.id if leela_offer else None,
            kind="offer_expired",
            message="An offer passed its acceptance deadline and was marked expired.",
            status="open",
        )
    )
    write_audit(
        db,
        actor_id=None,
        actor_email="system",
        actor_role="system",
        action="system.seed",
        entity_type="system",
        entity_id=None,
        before=None,
        after={"students": len(students), "session": "2026-27"},
        ip=None,
    )
    db.commit()
