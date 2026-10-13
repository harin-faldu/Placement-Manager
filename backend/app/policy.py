from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from app.domain import (
    PLACEMENT_LABELS,
    Check,
    DriveSnap,
    Evaluation,
    OfferSnap,
    StudentSnap,
    course_name,
)

IST = ZoneInfo("Asia/Kolkata")
RANK = {"C": 0, "B": 1, "A": 2, "A+": 3}


def money(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def category_for(ctc: float | None, config: dict) -> str | None:
    if ctc is None:
        return None
    value = money(ctc)
    if value >= money(config["a_plus_min"]):
        return "A+"
    if value >= money(config["a_min"]):
        return "A"
    if value >= money(config["b_min"]):
        return "B"
    return "C"


def accepted_offers(offers: list[OfferSnap]) -> list[OfferSnap]:
    return [offer for offer in offers if offer.acceptance_status == "accepted" and not offer.voided]


def governing_ctc(offers: list[OfferSnap]) -> float | None:
    values = [
        offer.ctc_lpa
        for offer in accepted_offers(offers)
        if offer.offer_type in {"F", "IF"} and offer.ctc_lpa is not None
    ]
    if not values:
        return None
    return float(max(money(value) for value in values))


def placement_status_of(offers: list[OfferSnap]) -> str:
    kinds = {offer.offer_type for offer in accepted_offers(offers)}
    if not kinds:
        return "unplaced"
    if "IF" in kinds or {"I", "F"} <= kinds:
        return "internship_ppo_fte"
    if "F" in kinds:
        return "fte_only"
    if "I" in kinds:
        return "internship_only"
    return "unplaced"


def acceptance_window(offer_date: date, company_hours: int | None, cap: int) -> tuple[datetime, int]:
    window = cap if not company_hours or company_hours < 1 else min(cap, int(company_hours))
    start = datetime.combine(offer_date, time(9, 0), tzinfo=IST)
    deadline = (start + timedelta(hours=window)).astimezone(timezone.utc).replace(tzinfo=None)
    return deadline, window


def narrative(config: dict) -> list[str]:
    return [
        f"A+ is {config['a_plus_min']:g} LPA or above. A package of exactly {config['a_plus_min']:g} LPA is A+. A student selected there leaves the placement process.",
        f"A is {config['a_min']:g} LPA up to, but not including, {config['a_plus_min']:g} LPA. A further packaged offer is allowed only in A+.",
        f"B is {config['b_min']:g} LPA up to, but not including, {config['a_min']:g} LPA. A further package must be at least {config['b_multiplier']:g}× the current package.",
        f"C is below {config['b_min']:g} LPA. Only a higher category is allowed.",
        "After an internship-only selection, another internship-only role is closed. FTE and internship + PPO/FTE stay open when the other rules allow them.",
        "After an FTE-only selection, another FTE-only role is closed, even if the category table would allow a higher package. An internship stays open when the other rules allow it.",
        "After internship + PPO/FTE, further internship, FTE, and internship + PPO/FTE roles at another organisation are closed.",
        "A move from an accepted FTE-only offer to internship + PPO/FTE is referred to the Placement Cell. It is not recorded as a silent approval.",
        f"Acceptance is due within the company timeline or {config['acceptance_hours_cap']} hours, whichever is earlier. The clock starts at 09:00 IST on the offer date.",
        f"An unexcused absence excludes the student from the next {config['absence_exclusion_drives']} drives. An emergency exception needs Placement Cell approval.",
        "Registration and company eligibility are checked before participation. The stricter result is the one that stands.",
        "These checks assist the Placement Cell. Disciplinary decisions and exceptions remain with the competent authority.",
    ]


def _finish(
    checks: list[Check],
    governing: float | None,
    category: str | None,
    status: str,
) -> Evaluation:
    if any(check.status == "fail" for check in checks):
        verdict = "block"
    elif any(check.status == "review" for check in checks):
        verdict = "review"
    else:
        verdict = "allow"
    return Evaluation(verdict, checks, governing, category, status)


def _add(checks: list[Check], code: str, title: str, status: str, detail: str) -> None:
    checks.append(Check(code, title, status, detail))


def evaluate(student: StudentSnap, offers: list[OfferSnap], drive: DriveSnap, config: dict) -> Evaluation:
    status = placement_status_of(offers)
    if student.archived:
        return _finish(
            [Check("record", "Student record", "fail", "This student record is archived and cannot enter a drive.")],
            None,
            None,
            status,
        )

    current = accepted_offers(offers)
    governing = governing_ctc(offers)
    category = category_for(governing, config) if governing is not None else None
    has_i = any(offer.offer_type == "I" for offer in current)
    has_f = any(offer.offer_type == "F" for offer in current)
    checks: list[Check] = []

    _add(checks, "record", "Student record", "pass", "The student record is active.")

    if student.registration_status == "registered":
        _add(checks, "registration", "Registration", "pass", "The student is registered for placement.")
    elif student.registration_status == "deregistered":
        _add(checks, "registration", "Registration", "fail", "A deregistered student does not enter further drives.")
    else:
        _add(checks, "registration", "Registration", "fail", "Placement registration is required before participation.")

    if student.eligibility_status == "eligible":
        _add(checks, "eligibility", "Eligibility", "pass", "Eligibility is marked eligible.")
    elif student.eligibility_status == "pending_verification":
        _add(checks, "eligibility", "Eligibility", "review", "Eligibility is still pending verification.")
    else:
        _add(checks, "eligibility", "Eligibility", "fail", "The student is marked ineligible.")

    if student.course in drive.courses:
        _add(
            checks,
            "programme",
            "Programme",
            "pass",
            f"{course_name(student.course)} is included in this drive.",
        )
    else:
        _add(
            checks,
            "programme",
            "Programme",
            "fail",
            f"This drive is not open to {course_name(student.course)}.",
        )

    if drive.min_cgpa is None:
        _add(checks, "academics", "Company cutoff", "pass", "This drive sets no CGPA cutoff.")
    elif student.cgpa is None:
        _add(checks, "academics", "Company cutoff", "review", "This drive has a CGPA cutoff and no CGPA is on record.")
    elif student.cgpa < drive.min_cgpa:
        _add(
            checks,
            "academics",
            "Company cutoff",
            "fail",
            f"CGPA {student.cgpa:.2f} is below this drive's cutoff of {drive.min_cgpa:.2f}.",
        )
    else:
        _add(
            checks,
            "academics",
            "Company cutoff",
            "pass",
            f"CGPA {student.cgpa:.2f} meets this drive's cutoff of {drive.min_cgpa:.2f}.",
        )

    if student.exclusion_drives_remaining > 0:
        _add(
            checks,
            "absence",
            "Attendance",
            "fail",
            f"An unexcused absence excludes this student from the next {student.exclusion_drives_remaining} drive(s).",
        )
    elif student.absence_review == "pending":
        _add(
            checks,
            "absence",
            "Attendance",
            "review",
            "An emergency exception is waiting for Placement Cell review.",
        )
    else:
        _add(checks, "absence", "Attendance", "pass", "No absence exclusion is active.")

    if category == "A+" and config.get("a_plus_exits_process", True):
        _add(
            checks,
            "a_plus",
            "A+ exit",
            "fail",
            f"The current package of {governing:.2f} LPA is A+. Students selected in A+ leave the placement process.",
        )
    elif category == "A+":
        _add(checks, "a_plus", "A+ exit", "pass", "The A+ exit rule is turned off in the current policy settings.")
    else:
        _add(checks, "a_plus", "A+ exit", "pass", "No A+ selection is on record.")

    other_if = [offer for offer in current if offer.offer_type == "IF" and offer.company_id != drive.company_id]
    same_if = [offer for offer in current if offer.offer_type == "IF" and offer.company_id == drive.company_id]
    if other_if and drive.offer_type in config.get("if_blocks_other_org", ["I", "F", "IF"]):
        _add(
            checks,
            "if_lock",
            "Internship + PPO/FTE",
            "fail",
            "An accepted internship + PPO/FTE closes internship, FTE, and internship + PPO/FTE roles at another organisation.",
        )
    elif same_if:
        _add(
            checks,
            "if_lock",
            "Internship + PPO/FTE",
            "review",
            "This student already holds internship + PPO/FTE at this organisation. A further role needs Placement Cell review.",
        )
    else:
        _add(checks, "if_lock", "Internship + PPO/FTE", "pass", "No internship + PPO/FTE selection closes this drive.")

    if has_i and drive.offer_type in config.get("i_blocks", ["I"]):
        _add(
            checks,
            "internship_lock",
            "Internship-only lock",
            "fail",
            "After an internship-only selection, the student cannot take another internship-only role.",
        )
    elif has_i:
        _add(
            checks,
            "internship_lock",
            "Internship-only lock",
            "pass",
            "The internship-only lock does not apply to this offer type.",
        )
    else:
        _add(checks, "internship_lock", "Internship-only lock", "pass", "No internship-only selection is on record.")

    fte_locked = has_f and drive.offer_type in config.get("f_blocks", ["F"])
    category_allows_switch = _category_allows(governing, category, drive, config)
    if fte_locked and config.get("category_can_override_fte_lock") and category_allows_switch:
        _add(
            checks,
            "fte_lock",
            "FTE-only lock",
            "pass",
            "The FTE-only lock is waived because the category rule allows this switch and the policy setting permits the waiver.",
        )
    elif fte_locked:
        _add(
            checks,
            "fte_lock",
            "FTE-only lock",
            "fail",
            "After an FTE-only selection, the student cannot take another FTE-only role.",
        )
    elif has_f:
        _add(checks, "fte_lock", "FTE-only lock", "pass", "The FTE-only lock does not apply to this offer type.")
    else:
        _add(checks, "fte_lock", "FTE-only lock", "pass", "No FTE-only selection is on record.")

    if has_f and drive.offer_type == "IF":
        mode = config.get("if_after_f", "review")
        if mode == "block":
            _add(
                checks,
                "if_after_fte",
                "FTE to internship + PPO/FTE",
                "fail",
                "The current policy blocks internship + PPO/FTE after an FTE-only selection.",
            )
        elif mode == "allow":
            _add(
                checks,
                "if_after_fte",
                "FTE to internship + PPO/FTE",
                "pass",
                "The current policy allows internship + PPO/FTE after an FTE-only selection when the other rules pass.",
            )
        else:
            _add(
                checks,
                "if_after_fte",
                "FTE to internship + PPO/FTE",
                "review",
                "Internship + PPO/FTE after an FTE-only selection is referred to the Placement Cell.",
            )
    else:
        _add(
            checks,
            "if_after_fte",
            "FTE to internship + PPO/FTE",
            "pass",
            "This is not a move from FTE-only to internship + PPO/FTE.",
        )

    _add(checks, "category", "Category switch", *_category_status(governing, category, drive, config))

    if any(offer.company_id == drive.company_id and offer.offer_type == drive.offer_type for offer in current):
        _add(
            checks,
            "same_company",
            "Existing selection",
            "fail",
            "An accepted offer of this type is already on record for this organisation.",
        )
    else:
        _add(checks, "same_company", "Existing selection", "pass", "No accepted offer of this type exists for this organisation.")

    pending_here = [
        offer
        for offer in offers
        if not offer.voided and offer.acceptance_status == "pending" and offer.company_id == drive.company_id
    ]
    pending_elsewhere = [
        offer
        for offer in offers
        if not offer.voided and offer.acceptance_status == "pending" and offer.company_id != drive.company_id
    ]
    if pending_here:
        _add(
            checks,
            "pending_offer",
            "Open offer",
            "review",
            "An offer at this organisation is still awaiting acceptance.",
        )
    elif pending_elsewhere:
        _add(
            checks,
            "pending_offer",
            "Open offer",
            "info",
            "Another offer is still awaiting acceptance. That deadline continues to apply.",
        )
    else:
        _add(checks, "pending_offer", "Open offer", "pass", "No offer is waiting for acceptance.")

    return _finish(checks, governing, category, status)


def _category_allows(
    governing: float | None,
    category: str | None,
    drive: DriveSnap,
    config: dict,
) -> bool:
    status, _detail = _category_status(governing, category, drive, config)
    return status == "pass"


def _category_status(
    governing: float | None,
    category: str | None,
    drive: DriveSnap,
    config: dict,
) -> tuple[str, str]:
    if drive.offer_type == "I" or drive.ctc_lpa is None:
        return "pass", "This drive has no FTE package, so the category switch rule is not applied."
    if governing is None or category is None:
        return "pass", "No accepted FTE package is on record, so there is no category ceiling."
    incoming = category_for(drive.ctc_lpa, config)
    if category == "A+":
        return "info", "The A+ rule is handled by the A+ exit check."
    if category == "A":
        if incoming == "A+":
            return (
                "pass",
                f"Category A ({governing:.2f} LPA) may switch only to A+. This offer is {drive.ctc_lpa:.2f} LPA (A+).",
            )
        return (
            "fail",
            f"Category A ({governing:.2f} LPA) may switch only to A+. This offer is {drive.ctc_lpa:.2f} LPA ({incoming}).",
        )
    if category == "B":
        required = money(governing) * money(config["b_multiplier"])
        required = required.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if money(drive.ctc_lpa) >= required:
            return (
                "pass",
                f"Category B requires at least {config['b_multiplier']:g}× {governing:.2f} LPA ({required} LPA). This offer is {drive.ctc_lpa:.2f} LPA.",
            )
        return (
            "fail",
            f"Category B requires at least {config['b_multiplier']:g}× the current package ({required} LPA). This offer is {drive.ctc_lpa:.2f} LPA.",
        )
    if incoming and RANK[incoming] > RANK["C"]:
        return (
            "pass",
            f"Category C ({governing:.2f} LPA) may move to a higher category. This offer is {incoming}.",
        )
    return (
        "fail",
        f"Category C ({governing:.2f} LPA) may move only to a higher category. This offer remains {incoming} at {drive.ctc_lpa:.2f} LPA.",
    )


def further_paths(student: StudentSnap, offers: list[OfferSnap], config: dict) -> dict[str, list[str]]:
    governing = governing_ctc(offers)
    floor = money(config["a_plus_min"])
    if governing is not None and category_for(governing, config) == "B":
        required = (money(governing) * money(config["b_multiplier"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if required > floor:
            floor = required
    package = float(floor)
    probes = [
        ("Internship", DriveSnap("probe-other", "I", None, [student.course], None)),
        ("FTE", DriveSnap("probe-other", "F", package, [student.course], None)),
        ("Internship + PPO/FTE", DriveSnap("probe-other", "IF", package, [student.course], None)),
    ]
    allow: list[str] = []
    review: list[str] = []
    for label, drive in probes:
        verdict = evaluate(student, offers, drive, config).verdict
        if verdict == "allow":
            allow.append(label)
        elif verdict == "review":
            review.append(label)
    return {"allow": allow, "review": review}


def standing(student: StudentSnap, offers: list[OfferSnap], config: dict) -> dict:
    paths = further_paths(student, offers, config)
    governing = governing_ctc(offers)
    category = category_for(governing, config) if governing is not None else None
    current = accepted_offers(offers)
    locks: list[str] = []
    if student.registration_status == "deregistered":
        locks.append("Deregistered from the placement process.")
    elif student.registration_status != "registered":
        locks.append("Not registered for placement.")
    if student.eligibility_status == "ineligible":
        locks.append("Marked ineligible.")
    elif student.eligibility_status == "pending_verification":
        locks.append("Eligibility is pending verification.")
    if student.exclusion_drives_remaining > 0:
        locks.append(f"Excluded from the next {student.exclusion_drives_remaining} drives.")
    elif student.absence_review == "pending":
        locks.append("An emergency absence exception is awaiting review.")
    if category == "A+" and config.get("a_plus_exits_process", True):
        locks.append(f"Selected in A+ at {governing:.2f} LPA and out of the placement process.")
    if any(offer.offer_type == "IF" for offer in current):
        locks.append("Internship + PPO/FTE closes other organisations.")
    if any(offer.offer_type == "I" for offer in current):
        locks.append("Internship-only selection blocks another internship-only role.")
    if any(offer.offer_type == "F" for offer in current):
        locks.append("FTE-only selection blocks another FTE-only role.")
    if category == "A":
        locks.append("Category A can switch only to an A+ package, and only when the offer-type rule also allows it.")
    elif category == "B" and governing is not None:
        required = (money(governing) * money(config["b_multiplier"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        locks.append(f"Category B needs a new package of at least {required} LPA.")
    elif category == "C":
        locks.append("Category C can move only to a higher category.")
    if not locks:
        locks.append("No active placement lock.")
    status = placement_status_of(offers)
    return {
        "placement_status": status,
        "placement_status_label": PLACEMENT_LABELS[status],
        "governing_ctc": governing,
        "governing_category": category,
        "further_allow": paths["allow"],
        "further_review": paths["review"],
        "locks": locks,
    }
