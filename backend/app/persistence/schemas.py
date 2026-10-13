from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.validate import clean_batch, clean_email, clean_mobile, clean_name, clean_placement_id, clean_text, resolve_course


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return clean_email(value)


class MfaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge: str = Field(min_length=10, max_length=200)
    code: str = Field(min_length=6, max_length=8)


class MfaConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=6, max_length=8)


class StudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placement_id: str
    full_name: str
    mobile: str
    email: EmailStr
    course: str
    batch: str
    registration_status: Literal["registered", "deregistered", "not_registered"] = "not_registered"
    eligibility_status: Literal["eligible", "ineligible", "pending_verification"] = "pending_verification"
    cgpa: float | None = Field(default=None, ge=0, le=10)
    remarks: str | None = None

    @field_validator("placement_id")
    @classmethod
    def pid(cls, value: str) -> str:
        return clean_placement_id(value)

    @field_validator("full_name")
    @classmethod
    def name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("mobile")
    @classmethod
    def mobile_ok(cls, value: str) -> str:
        return clean_mobile(value)

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        return clean_email(value)

    @field_validator("course")
    @classmethod
    def course_ok(cls, value: str) -> str:
        return resolve_course(value)

    @field_validator("batch")
    @classmethod
    def batch_ok(cls, value: str) -> str:
        return clean_batch(value)

    @field_validator("remarks")
    @classmethod
    def remarks_ok(cls, value: str | None) -> str | None:
        return clean_text(value)


class StudentProvision(StudentCreate):
    password: str = Field(min_length=10, max_length=200)


class StudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = None
    mobile: str | None = None
    email: EmailStr | None = None
    course: str | None = None
    batch: str | None = None
    registration_status: Literal["registered", "deregistered", "not_registered"] | None = None
    eligibility_status: Literal["eligible", "ineligible", "pending_verification"] | None = None
    cgpa: float | None = Field(default=None, ge=0, le=10)
    remarks: str | None = None

    @field_validator("full_name")
    @classmethod
    def name(cls, value: str | None) -> str | None:
        return clean_name(value) if value is not None else None

    @field_validator("mobile")
    @classmethod
    def mobile_ok(cls, value: str | None) -> str | None:
        return clean_mobile(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: EmailStr | None) -> str | None:
        return clean_email(str(value)) if value is not None else None

    @field_validator("course")
    @classmethod
    def course_ok(cls, value: str | None) -> str | None:
        return resolve_course(value) if value is not None else None

    @field_validator("batch")
    @classmethod
    def batch_ok(cls, value: str | None) -> str | None:
        return clean_batch(value) if value is not None else None

    @field_validator("remarks")
    @classmethod
    def remarks_ok(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None


class ExclusionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["clear", "impose"]
    reason: str = Field(min_length=4, max_length=500)


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_ok(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("notes")
    @classmethod
    def notes_ok(cls, value: str | None) -> str | None:
        return clean_text(value)


class DriveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: str
    title: str = Field(min_length=2, max_length=160)
    offer_type: Literal["I", "F", "IF"]
    ctc_lpa: float | None = None
    stipend_amount: float | None = None
    stipend_period: Literal["monthly", "total"] | None = None
    acceptance_hours: int | None = Field(default=None, ge=1, le=168)
    courses: list[str] = Field(min_length=1)
    min_cgpa: float | None = Field(default=None, ge=0, le=10)
    scheduled_on: date | None = None
    notes: str | None = None

    @field_validator("title")
    @classmethod
    def title_ok(cls, value: str) -> str:
        cleaned = clean_text(value, 160)
        if not cleaned:
            raise ValueError("Enter a drive title")
        return cleaned

    @field_validator("notes")
    @classmethod
    def notes_ok(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("courses")
    @classmethod
    def courses_ok(cls, value: list[str]) -> list[str]:
        return [resolve_course(item) for item in value]


class OfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str
    drive_id: str | None = None
    company_id: str | None = None
    offer_type: Literal["I", "F", "IF"] | None = None
    ctc_lpa: float | None = None
    stipend_amount: float | None = None
    stipend_period: Literal["monthly", "total"] | None = None
    ppo_status: Literal["na", "pending", "offered", "accepted", "declined"] | None = None
    acceptance_status: Literal["pending", "accepted", "declined"] = "pending"
    joining_status: Literal["pending", "joined", "not_joined"] = "pending"
    offer_date: date
    is_off_campus: bool = False
    noc_status: Literal["not_required", "pending", "issued", "rejected"] = "not_required"
    acceptance_hours: int | None = Field(default=None, ge=1, le=168)
    remarks: str | None = None
    override_reason: str | None = None

    @field_validator("remarks", "override_reason")
    @classmethod
    def text_ok(cls, value: str | None) -> str | None:
        return clean_text(value, 500)


class OfferPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acceptance_status: Literal["pending", "accepted", "declined"] | None = None
    joining_status: Literal["pending", "joined", "not_joined"] | None = None
    ppo_status: Literal["na", "pending", "offered", "accepted", "declined"] | None = None
    noc_status: Literal["not_required", "pending", "issued", "rejected"] | None = None
    remarks: str | None = None
    override_reason: str | None = None

    @field_validator("remarks", "override_reason")
    @classmethod
    def text_ok(cls, value: str | None) -> str | None:
        return clean_text(value, 500)


class OfferVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=4, max_length=500)


class AttendanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str
    activity: Literal["ppt", "test", "interview", "other"]
    attended: bool
    emergency_claimed: bool = False
    note: str | None = None

    @field_validator("note")
    @classmethod
    def note_ok(cls, value: str | None) -> str | None:
        return clean_text(value, 500)


class AttendanceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=4, max_length=500)


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str


class PolicyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str
    drive_id: str


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a_plus_min: float = Field(gt=0, le=200)
    a_min: float = Field(gt=0, le=200)
    b_min: float = Field(gt=0, le=200)
    b_multiplier: float = Field(ge=1, le=5)
    acceptance_hours_cap: int = Field(ge=1, le=72)
    absence_exclusion_drives: int = Field(ge=0, le=10)
    a_plus_exits_process: bool
    category_can_override_fte_lock: bool
    if_after_f: Literal["review", "block", "allow"]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    full_name: str
    password: str = Field(min_length=10, max_length=200)
    role: Literal["admin", "officer", "coordinator", "recruiter", "student"]
    course: str | None = None
    company_id: str | None = None
    student_id: str | None = None

    @field_validator("email")
    @classmethod
    def email_ok(cls, value: str) -> str:
        return clean_email(value)

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("course")
    @classmethod
    def course_ok(cls, value: str | None) -> str | None:
        return resolve_course(value) if value else None


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool | None = None
    role: Literal["admin", "officer", "coordinator", "recruiter", "student"] | None = None
    course: str | None = None
    company_id: str | None = None

    @field_validator("course")
    @classmethod
    def course_ok(cls, value: str | None) -> str | None:
        return resolve_course(value) if value else None


class FlagResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=4, max_length=500)
