from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import utcnow
from app.database import Base


def _id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), index=True)
    course: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MfaChallenge(Base):
    __tablename__ = "mfa_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    drives: Mapped[list[Drive]] = relationship(back_populates="company")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("placement_id", name="uq_students_placement_id"),
        UniqueConstraint("email", name="uq_students_email"),
        UniqueConstraint("mobile_hash", name="uq_students_mobile_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    placement_id: Mapped[str] = mapped_column(String(40), index=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    email: Mapped[str] = mapped_column(String(255))
    mobile_encrypted: Mapped[str] = mapped_column(Text)
    mobile_hash: Mapped[str] = mapped_column(String(64))
    course: Mapped[str] = mapped_column(String(64), index=True)
    batch: Mapped[str] = mapped_column(String(8), index=True)
    registration_status: Mapped[str] = mapped_column(String(32), default="not_registered")
    eligibility_status: Mapped[str] = mapped_column(String(32), default="pending_verification")
    placement_status: Mapped[str] = mapped_column(String(32), default="unplaced", index=True)
    cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclusion_drives_remaining: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Drive(Base):
    __tablename__ = "drives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    offer_type: Mapped[str] = mapped_column(String(8))
    ctc_lpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    stipend_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    stipend_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    acceptance_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    courses_json: Mapped[str] = mapped_column(Text)
    min_cgpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    scheduled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    company: Mapped[Company] = relationship(back_populates="drives")


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    drive_id: Mapped[str | None] = mapped_column(ForeignKey("drives.id"), nullable=True)
    offer_type: Mapped[str] = mapped_column(String(8))
    category: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ctc_lpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    stipend_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    stipend_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ppo_status: Mapped[str] = mapped_column(String(16), default="na")
    acceptance_status: Mapped[str] = mapped_column(String(16), default="pending")
    joining_status: Mapped[str] = mapped_column(String(16), default="pending")
    offer_date: Mapped[date] = mapped_column(Date)
    acceptance_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acceptance_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_off_campus: Mapped[bool] = mapped_column(Boolean, default=False)
    noc_status: Mapped[str] = mapped_column(String(32), default="not_required")
    voided: Mapped[bool] = mapped_column(Boolean, default=False)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OfferEvent(Base):
    __tablename__ = "offer_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    activity: Mapped[str] = mapped_column(String(32))
    attended: Mapped[bool] = mapped_column(Boolean, default=True)
    emergency_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(16), default="none")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExclusionCharge(Base):
    __tablename__ = "exclusion_charges"
    __table_args__ = (UniqueConstraint("student_id", "drive_id", name="uq_exclusion_student_drive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ComplianceFlag(Base):
    __tablename__ = "compliance_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"), nullable=True)
    drive_id: Mapped[str | None] = mapped_column(ForeignKey("drives.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    row_hash: Mapped[str] = mapped_column(String(64))


class PolicyConfig(Base):
    __tablename__ = "policy_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
