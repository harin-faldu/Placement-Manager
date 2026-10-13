import os
from datetime import timedelta

import pyotp
import pytest
from sqlalchemy import select, text

from app.core.clock import today_ist, utcnow
from app.core.database import SessionLocal
from app.persistence.models import AuditLog, UserSession

HEADER = {"X-Requested-With": "placement"}


def login(client, email, password=None):
    if password is None:
        password = os.environ["ADMIN_PASSWORD"]
    response = client.post("/api/auth/login", json={"email": email, "password": password}, headers=HEADER)
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_and_role_labels(client):
    payload = login(client, "admin@nfsu.ac.in")
    assert payload["user"]["role_label"] == "Placement Administrator"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "admin@nfsu.ac.in"


def test_duplicate_placement_id_is_rejected(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    body = {
        "placement_id": "NFSU-2026-001",
        "full_name": "Copy Student",
        "mobile": "9010000099",
        "email": "copy.student@nfsu.ac.in",
        "course": "MTECH_CS",
        "batch": "2026",
        "registration_status": "registered",
        "eligibility_status": "eligible",
    }
    response = client.post("/api/students", json=body, headers=HEADER)
    assert response.status_code == 409
    assert "Placement ID" in response.json()["detail"]


def test_markup_in_a_name_is_rejected(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    body = {
        "placement_id": "NFSU-2026-777",
        "full_name": "<script>alert(1)</script>",
        "mobile": "9010000088",
        "email": "script.student@nfsu.ac.in",
        "course": "MTECH_CS",
        "batch": "2026",
    }
    response = client.post("/api/students", json=body, headers=HEADER)
    assert response.status_code == 422


def test_search_is_parameterised(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    hostile = client.get("/api/students", params={"q": "'; DROP TABLE students;--"})
    assert hostile.status_code == 200
    again = client.get("/api/students")
    assert again.status_code == 200
    assert again.json()["total"] > 0


def test_student_cannot_read_or_edit_another_record(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    listing = client.get("/api/students", params={"q": "Aisha"}).json()
    aisha = listing["items"][0]["id"]
    client.post("/api/auth/logout", headers=HEADER)
    login(client, "ananya.shah@nfsu.ac.in", os.environ["STUDENT_PASSWORD"])
    assert client.get("/api/students").status_code == 403
    denied = client.get(f"/api/students/{aisha}")
    assert denied.status_code == 404
    assert "mobile" not in denied.text or "9010000001" not in denied.text
    me = client.get("/api/auth/me").json()["user"]
    own = client.get(f"/api/students/{me['student_id']}")
    assert own.status_code == 200
    assert own.json()["student"]["full_name"] == "Ananya Shah"
    patched = client.patch(
        f"/api/students/{me['student_id']}",
        json={"placement_status": "fte_only", "remarks": "self edit"},
        headers=HEADER,
    )
    assert patched.status_code == 403
    offered = client.post(
        "/api/offers",
        json={"student_id": me["student_id"], "offer_date": today_ist().isoformat(), "company_id": "x", "offer_type": "F", "ctc_lpa": 20},
        headers=HEADER,
    )
    assert offered.status_code == 403


def test_placement_status_cannot_be_assigned_directly(client):
    login(client, "admin@nfsu.ac.in")
    ananya = client.get("/api/students", params={"q": "Ananya"}).json()["items"][0]
    response = client.patch(
        f"/api/students/{ananya['id']}",
        json={"placement_status": "fte_only"},
        headers=HEADER,
    )
    assert response.status_code == 422
    again = client.get(f"/api/students/{ananya['id']}")
    assert again.json()["student"]["placement_status"] == "unplaced"


def test_coordinator_is_limited_to_one_programme(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    neel = client.get("/api/students", params={"q": "Neel Kapoor"}).json()["items"][0]
    aisha = client.get("/api/students", params={"q": "Aisha"}).json()["items"][0]
    client.post("/api/auth/logout", headers=HEADER)
    login(client, "coord.cs@nfsu.ac.in", os.environ["COORDINATOR_PASSWORD"])
    assert client.get(f"/api/students/{neel['id']}").status_code == 404
    assert client.get(f"/api/students/{aisha['id']}").status_code == 200
    blocked = client.patch(
        f"/api/students/{aisha['id']}",
        json={"registration_status": "deregistered"},
        headers=HEADER,
    )
    assert blocked.status_code == 403
    assert client.get("/api/students", params={"course": "MSC_DFIS"}).status_code == 403


def test_drive_package_cannot_be_overstated_by_the_client(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    ananya = client.get("/api/students", params={"q": "Ananya"}).json()["items"][0]
    drives = client.get("/api/drives").json()["items"]
    fieldnote = next(item for item in drives if item["title"] == "Fieldnote FTE")
    response = client.post(
        "/api/offers",
        json={
            "student_id": ananya["id"],
            "drive_id": fieldnote["id"],
            "ctc_lpa": 40,
            "offer_type": "F",
            "offer_date": today_ist().isoformat(),
            "acceptance_status": "accepted",
        },
        headers=HEADER,
    )
    assert response.status_code == 200, response.text
    offer = response.json()["offer"]
    assert offer["ctc_lpa"] == 4.5
    assert offer["category"] == "C"


def test_switching_rules_block_a_second_fte(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    rohan = client.get("/api/students", params={"q": "Rohan"}).json()["items"][0]
    drives = client.get("/api/drives").json()["items"]
    kavach = next(item for item in drives if item["title"] == "Kavach FTE 2026")
    preview = client.post("/api/policy/check", json={"student_id": rohan["id"], "drive_id": kavach["id"]}, headers=HEADER)
    assert preview.status_code == 200
    assert preview.json()["verdict"] == "block"
    created = client.post(
        "/api/offers",
        json={"student_id": rohan["id"], "drive_id": kavach["id"], "offer_date": today_ist().isoformat()},
        headers=HEADER,
    )
    assert created.status_code == 409
    assert created.json()["detail"]["evaluation"]["verdict"] == "block"


def test_administrator_override_is_audited(client):
    login(client, "admin@nfsu.ac.in")
    rohan = client.get("/api/students", params={"q": "Rohan"}).json()["items"][0]
    drives = client.get("/api/drives").json()["items"]
    kavach = next(item for item in drives if item["title"] == "Kavach FTE 2026")
    created = client.post(
        "/api/offers",
        json={
            "student_id": rohan["id"],
            "drive_id": kavach["id"],
            "offer_date": today_ist().isoformat(),
            "override_reason": "Written exception approved by the cell",
        },
        headers=HEADER,
    )
    assert created.status_code == 200, created.text
    assert created.json()["offer"]["policy_verdict"] == "override"
    report = client.get("/api/reports/overview").json()
    assert any(item["kind"] == "policy_override" for item in report["attention"])


def test_recruiter_sees_no_contact_or_pay(client):
    login(client, "recruiter@kavach.example", os.environ["RECRUITER_PASSWORD"])
    assert client.get("/api/students").status_code == 403
    drives = client.get("/api/drives").json()["items"]
    assert drives
    assert all(item["company_name"] == "Kavach Security" for item in drives)
    internship = next(item for item in drives if item["offer_type"] == "I")
    payload = client.get(f"/api/drives/{internship['id']}/candidates").json()
    assert payload["eligible_count"] >= 1
    assert payload["withheld_count"] >= 1
    for person in payload["eligible"]:
        assert "mobile" not in person
        assert "email" not in person
        assert "placement_id" not in person
        assert "ctc_lpa" not in person


def test_reports_separate_people_packages_and_stipends(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    report = client.get("/api/reports/overview").json()
    totals = report["totals"]
    assert totals["placed"] == 8
    assert totals["offers"] == 10
    assert totals["accepted_offers"] == 8
    assert totals["placed"] == totals["fte_only"] + totals["internship_only"] + totals["internship_ppo_fte"]
    assert report["ctc"]["highest"] == 22
    assert report["ctc"]["median"] == 11.5
    assert report["ctc"]["average"] == 12.58
    assert report["stipend_monthly"]["median"] == 25000
    assert report["stipend_monthly"]["highest"] == 40000
    assert len(report["by_course"]) == 5


def test_officer_cannot_change_policy_or_archive(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    ananya = client.get("/api/students", params={"q": "Ananya"}).json()["items"][0]
    assert client.post(f"/api/students/{ananya['id']}/archive", headers=HEADER).status_code == 403
    current = client.get("/api/policy").json()["config"]
    assert client.put("/api/policy", json=current, headers=HEADER).status_code == 403


def test_export_is_audited_and_coordinator_export_stays_in_programme(client):
    login(client, "coord.cs@nfsu.ac.in", os.environ["COORDINATOR_PASSWORD"])
    response = client.get("/api/exports/students")
    assert response.status_code == 200
    assert "mobile" in response.text
    assert "MTECH_AIDS" not in response.text
    assert "NFSU-2026-001" in response.text
    client.post("/api/auth/logout", headers=HEADER)
    login(client, "admin@nfsu.ac.in")
    actions = [item["action"] for item in client.get("/api/audit").json()["items"]]
    assert "student.export" in actions


def test_audit_chain_rejects_tampering(client):
    login(client, "admin@nfsu.ac.in")
    assert client.post("/api/audit/verify", headers=HEADER).json()["valid"] is True
    db = SessionLocal()
    try:
        with pytest.raises(Exception):
            db.execute(text("UPDATE audit_logs SET payload = 'tamper' WHERE id = 1"))
            db.commit()
    finally:
        db.rollback()
        db.close()
    rows = SessionLocal()
    try:
        assert rows.get(AuditLog, 1) is not None
    finally:
        rows.close()


def test_idle_session_expires(client):
    login(client, "admin@nfsu.ac.in")
    db = SessionLocal()
    try:
        session = db.scalar(select(UserSession).order_by(UserSession.created_at.desc()))
        session.last_seen_at = utcnow() - timedelta(minutes=31)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/auth/me").status_code == 401


def test_optional_mfa(client):
    login(client, "admin@nfsu.ac.in")
    secret = client.post("/api/auth/mfa/setup", headers=HEADER).json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert client.post("/api/auth/mfa/confirm", json={"code": code}, headers=HEADER).status_code == 200
    client.post("/api/auth/logout", headers=HEADER)
    challenge = client.post(
        "/api/auth/login",
        json={"email": "admin@nfsu.ac.in", "password": os.environ["ADMIN_PASSWORD"]},
        headers=HEADER,
    ).json()
    assert challenge["mfa_required"] is True
    rejected = client.post(
        "/api/auth/mfa",
        json={"challenge": challenge["challenge"], "code": "000000"},
        headers=HEADER,
    )
    assert rejected.status_code == 401
    accepted = client.post(
        "/api/auth/mfa",
        json={"challenge": challenge["challenge"], "code": pyotp.TOTP(secret).now()},
        headers=HEADER,
    )
    assert accepted.status_code == 200


def test_login_is_rate_limited(client):
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@nfsu.ac.in", "password": "Wrong@12345"},
            headers=HEADER,
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/auth/login",
        json={"email": "nobody@nfsu.ac.in", "password": "Wrong@12345"},
        headers=HEADER,
    )
    assert blocked.status_code == 429


def test_mutation_without_request_context_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": "admin@nfsu.ac.in", "password": os.environ["ADMIN_PASSWORD"]})
    assert response.status_code == 403


def test_drive_precheck_explains_blocks_and_hides_them_from_recruiters(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    drives = client.get("/api/drives").json()["items"]
    kavach = next(item for item in drives if item["title"] == "Kavach FTE 2026")
    precheck = client.get(f"/api/drives/{kavach['id']}/precheck")
    assert precheck.status_code == 200
    body = precheck.json()
    assert body["block"] >= 1
    rohan = next(item for item in body["items"] if item["full_name"] == "Rohan Mehta")
    assert rohan["verdict"] == "block"
    assert any("FTE" in reason or "offer type" in reason.lower() or "already" in reason.lower() for reason in rohan["reasons"])
    client.post("/api/auth/logout", headers=HEADER)
    login(client, "recruiter@kavach.example", os.environ["RECRUITER_PASSWORD"])
    denied = client.get(f"/api/drives/{kavach['id']}/precheck")
    assert denied.status_code == 403
    candidates = client.get(f"/api/drives/{kavach['id']}/candidates").json()
    assert "reasons" not in candidates
    assert all("reasons" not in row for row in candidates["eligible"])


def test_exception_resolution_records_officer_and_justification(client):
    login(client, "officer@nfsu.ac.in", os.environ["OFFICER_PASSWORD"])
    queue = client.get("/api/compliance")
    assert queue.status_code == 200
    open_flag = next(item for item in queue.json()["items"] if item["status"] == "open" and item["kind"] == "offer_expired")
    resolved = client.post(
        f"/api/compliance/{open_flag['id']}/resolve",
        json={"note": "Company closed the role after the deadline."},
        headers=HEADER,
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["resolved_by"] == "officer@nfsu.ac.in"
    assert payload["resolution_note"] == "Company closed the role after the deadline."
    again = client.get("/api/compliance").json()["items"]
    stored = next(item for item in again if item["id"] == open_flag["id"])
    assert stored["status"] == "resolved"
    assert stored["resolved_by"] == "officer@nfsu.ac.in"
