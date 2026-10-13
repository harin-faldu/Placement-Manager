from __future__ import annotations

from dataclasses import asdict, dataclass, field

COURSES: list[dict[str, str]] = [
    {"code": "MTECH_CS", "name": "M.Tech. Computer Science", "short": "M.Tech. CS"},
    {
        "code": "MTECH_AIDS",
        "name": "M.Tech. Artificial Intelligence and Data Science",
        "short": "M.Tech. AIDS",
    },
    {
        "code": "BTECH_MTECH_CSE",
        "name": "B.Tech.–M.Tech. Computer Science and Engineering",
        "short": "B.Tech.–M.Tech. CSE",
    },
    {"code": "MSC_CS", "name": "M.Sc. Computer Science", "short": "M.Sc. CS"},
    {
        "code": "MSC_DFIS",
        "name": "M.Sc. Digital Forensics and Information Security",
        "short": "M.Sc. DFIS",
    },
]

ROLE_LABELS = {
    "admin": "Placement Administrator",
    "officer": "Placement Officer",
    "coordinator": "Course Coordinator",
    "recruiter": "Company / Recruiter",
    "student": "Student",
}

PLACEMENT_LABELS = {
    "unplaced": "Unplaced",
    "internship_only": "Internship only",
    "fte_only": "FTE only",
    "internship_ppo_fte": "Internship + PPO/FTE",
}

OFFER_LABELS = {
    "I": "Internship only",
    "F": "FTE only",
    "IF": "Internship + PPO/FTE",
}

REGISTRATION_LABELS = {
    "registered": "Registered",
    "deregistered": "Deregistered",
    "not_registered": "Not registered",
}

ELIGIBILITY_LABELS = {
    "eligible": "Eligible",
    "ineligible": "Ineligible",
    "pending_verification": "Pending verification",
}

DEFAULT_CONFIG: dict = {
    "a_plus_min": 16,
    "a_min": 10,
    "b_min": 6,
    "b_multiplier": 1.5,
    "acceptance_hours_cap": 24,
    "absence_exclusion_drives": 3,
    "a_plus_exits_process": True,
    "category_can_override_fte_lock": False,
    "if_after_f": "review",
    "i_blocks": ["I"],
    "f_blocks": ["F"],
    "if_blocks_other_org": ["I", "F", "IF"],
}


def course_by_code(code: str) -> dict[str, str] | None:
    for course in COURSES:
        if course["code"] == code:
            return course
    return None


def course_name(code: str) -> str:
    found = course_by_code(code)
    return found["name"] if found else code


def course_short(code: str) -> str:
    found = course_by_code(code)
    return found["short"] if found else code


@dataclass
class StudentSnap:
    id: str
    placement_id: str
    full_name: str
    course: str
    batch: str
    registration_status: str
    eligibility_status: str
    cgpa: float | None
    exclusion_drives_remaining: int
    absence_review: str
    archived: bool


@dataclass
class OfferSnap:
    id: str
    student_id: str
    company_id: str
    company_name: str
    offer_type: str
    ctc_lpa: float | None
    stipend_amount: float | None
    stipend_period: str | None
    acceptance_status: str
    joining_status: str
    ppo_status: str
    voided: bool
    is_off_campus: bool = False


@dataclass
class DriveSnap:
    company_id: str
    offer_type: str
    ctc_lpa: float | None
    courses: list[str]
    min_cgpa: float | None
    company_hours: int | None = None


@dataclass
class FlagSnap:
    student_id: str
    kind: str
    message: str


@dataclass
class Check:
    code: str
    title: str
    status: str
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Evaluation:
    verdict: str
    checks: list[Check] = field(default_factory=list)
    governing_ctc: float | None = None
    governing_category: str | None = None
    placement_status: str = "unplaced"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "checks": [check.as_dict() for check in self.checks],
            "governing_ctc": self.governing_ctc,
            "governing_category": self.governing_category,
            "placement_status": self.placement_status,
            "placement_status_label": PLACEMENT_LABELS.get(self.placement_status, self.placement_status),
        }
