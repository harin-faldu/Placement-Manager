from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.domain import COURSES, FlagSnap, OfferSnap, StudentSnap, course_name, course_short
from app.policy import category_for, further_paths, governing_ctc, placement_status_of

DEFINITIONS = {
    "registered": "Students whose placement registration is Registered. Archived records are excluded.",
    "eligible": "Students marked Eligible. This can overlap with placed and unplaced.",
    "ineligible": "Students marked Ineligible.",
    "placed": "Unique students with at least one accepted offer. A person is counted once, however many offers they hold.",
    "unplaced": "Registered students with no accepted offer. This includes students who are still pending verification or ineligible.",
    "offers": "Offer events that have not been voided, including pending, declined, and expired offers.",
    "ctc": "Highest accepted annual FTE package per student, in LPA, from FTE-only and internship + PPO/FTE offers. Stipends are not included.",
    "stipend": "Highest accepted monthly internship stipend per student. Annual CTC is not included.",
    "further": "Students for whom the switching and offer-type rules still allow at least one further path. A specific drive can still fail its own cutoff.",
}


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    total = sum((Decimal(str(value)) for value in values), Decimal("0"))
    return float((total / Decimal(len(values))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(Decimal(str(value)) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float(((ordered[mid - 1] + ordered[mid]) / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _highest(values: list[float]) -> float | None:
    if not values:
        return None
    return float(max(Decimal(str(value)) for value in values))


def _pack(values: list[float]) -> dict:
    return {
        "highest": _highest(values),
        "average": _average(values),
        "median": _median(values),
        "count": len(values),
    }


def summarize(
    students: list[StudentSnap],
    offers: list[OfferSnap],
    flags: list[FlagSnap],
    config: dict,
) -> dict:
    active = [student for student in students if not student.archived]
    active_ids = {student.id for student in active}
    live_offers = [offer for offer in offers if not offer.voided and offer.student_id in active_ids]
    accepted = [offer for offer in live_offers if offer.acceptance_status == "accepted"]

    by_student: dict[str, list[OfferSnap]] = defaultdict(list)
    for offer in live_offers:
        by_student[offer.student_id].append(offer)

    status_of = {student.id: placement_status_of(by_student.get(student.id, [])) for student in active}
    placed_ids = {student_id for student_id, status in status_of.items() if status != "unplaced"}

    packages: list[float] = []
    stipends: list[float] = []
    other_stipends = 0
    for student in active:
        own = by_student.get(student.id, [])
        package = governing_ctc(own)
        if package is not None:
            packages.append(package)
        monthly = [
            offer.stipend_amount
            for offer in own
            if offer.acceptance_status == "accepted"
            and offer.stipend_amount is not None
            and offer.stipend_period == "monthly"
        ]
        if monthly:
            stipends.append(max(monthly))
        other_stipends += sum(
            1
            for offer in own
            if offer.acceptance_status == "accepted"
            and offer.stipend_amount is not None
            and offer.stipend_period not in {None, "monthly"}
        )

    further_eligible = 0
    further_review = 0
    for student in active:
        paths = further_paths(student, by_student.get(student.id, []), config)
        if paths["allow"]:
            further_eligible += 1
        elif paths["review"]:
            further_review += 1

    def course_row(code: str, name: str, short: str, cohort: list[StudentSnap]) -> dict:
        ids = {student.id for student in cohort}
        cohort_offers = [offer for offer in accepted if offer.student_id in ids and offer.offer_type in {"F", "IF"}]
        per_student: dict[str, float] = {}
        for offer in cohort_offers:
            if offer.ctc_lpa is None:
                continue
            per_student[offer.student_id] = max(per_student.get(offer.student_id, 0), offer.ctc_lpa)
        return {
            "course": code,
            "name": name,
            "short": short,
            "students": len(cohort),
            "registered": sum(1 for student in cohort if student.registration_status == "registered"),
            "eligible": sum(1 for student in cohort if student.eligibility_status == "eligible"),
            "placed": sum(1 for student in cohort if student.id in placed_ids),
            "unplaced": sum(
                1
                for student in cohort
                if student.registration_status == "registered" and student.id not in placed_ids
            ),
            "internship_only": sum(1 for student in cohort if status_of[student.id] == "internship_only"),
            "fte_only": sum(1 for student in cohort if status_of[student.id] == "fte_only"),
            "internship_ppo_fte": sum(1 for student in cohort if status_of[student.id] == "internship_ppo_fte"),
            "median_ctc": _median(list(per_student.values())),
        }

    by_course = []
    seen = set()
    for course in COURSES:
        cohort = [student for student in active if student.course == course["code"]]
        seen.add(course["code"])
        by_course.append(course_row(course["code"], course["name"], course["short"], cohort))
    for code in sorted({student.course for student in active} - seen):
        cohort = [student for student in active if student.course == code]
        by_course.append(course_row(code, course_name(code), course_short(code), cohort))

    batches = sorted({student.batch for student in active})
    by_batch = []
    for batch in batches:
        cohort = [student for student in active if student.batch == batch]
        by_batch.append(
            {
                "batch": batch,
                "students": len(cohort),
                "registered": sum(1 for student in cohort if student.registration_status == "registered"),
                "placed": sum(1 for student in cohort if student.id in placed_ids),
                "unplaced": sum(
                    1
                    for student in cohort
                    if student.registration_status == "registered" and student.id not in placed_ids
                ),
                "median_ctc": course_row(batch, batch, batch, cohort)["median_ctc"],
            }
        )

    company_ids = []
    for offer in live_offers:
        if offer.company_id not in company_ids:
            company_ids.append(offer.company_id)
    by_company = []
    for company_id in company_ids:
        rows = [offer for offer in live_offers if offer.company_id == company_id]
        accepted_rows = [offer for offer in rows if offer.acceptance_status == "accepted"]
        ctc_values = [offer.ctc_lpa for offer in accepted_rows if offer.offer_type in {"F", "IF"} and offer.ctc_lpa is not None]
        categories = []
        for offer in accepted_rows:
            label = category_for(offer.ctc_lpa, config) if offer.offer_type in {"F", "IF"} else None
            if label and label not in categories:
                categories.append(label)
        by_company.append(
            {
                "company_id": company_id,
                "company": rows[0].company_name,
                "offers": len(rows),
                "accepted": len(accepted_rows),
                "categories": categories,
                "average_ctc": _average([value for value in ctc_values if value is not None]),
                "offer_types": sorted({offer.offer_type for offer in rows}),
            }
        )

    names = {student.id: student for student in active}
    attention = []
    for student in active:
        if student.eligibility_status == "pending_verification":
            attention.append(_attention(student, "eligibility", "Eligibility is pending verification."))
        if student.absence_review == "excluded" and student.exclusion_drives_remaining > 0:
            attention.append(
                _attention(
                    student,
                    "absence",
                    f"Excluded from the next {student.exclusion_drives_remaining} drives.",
                )
            )
        elif student.absence_review == "pending":
            attention.append(_attention(student, "absence", "Emergency absence exception is awaiting review."))
    for offer in live_offers:
        student = names.get(offer.student_id)
        if student is None:
            continue
        if offer.acceptance_status == "pending":
            attention.append(_attention(student, "acceptance", f"Offer from {offer.company_name} is awaiting acceptance."))
        if offer.acceptance_status == "accepted" and offer.joining_status == "pending":
            attention.append(_attention(student, "joining", f"Joining at {offer.company_name} is still pending."))
    for flag in flags:
        student = names.get(flag.student_id)
        if student is None:
            continue
        attention.append(_attention(student, flag.kind, flag.message))

    return {
        "definitions": DEFINITIONS,
        "totals": {
            "records": len(active),
            "registered": sum(1 for student in active if student.registration_status == "registered"),
            "not_registered": sum(1 for student in active if student.registration_status == "not_registered"),
            "deregistered": sum(1 for student in active if student.registration_status == "deregistered"),
            "eligible": sum(1 for student in active if student.eligibility_status == "eligible"),
            "ineligible": sum(1 for student in active if student.eligibility_status == "ineligible"),
            "pending_verification": sum(1 for student in active if student.eligibility_status == "pending_verification"),
            "placed": len(placed_ids),
            "unplaced": sum(
                1
                for student in active
                if student.registration_status == "registered" and student.id not in placed_ids
            ),
            "internship_only": sum(1 for status in status_of.values() if status == "internship_only"),
            "fte_only": sum(1 for status in status_of.values() if status == "fte_only"),
            "internship_ppo_fte": sum(1 for status in status_of.values() if status == "internship_ppo_fte"),
            "offers": len(live_offers),
            "accepted_offers": len(accepted),
            "off_campus_accepted": sum(1 for offer in accepted if offer.is_off_campus),
            "further_eligible": further_eligible,
            "further_review": further_review,
            "pending_acceptance": sum(1 for offer in live_offers if offer.acceptance_status == "pending"),
            "pending_joining": sum(
                1 for offer in accepted if offer.joining_status == "pending"
            ),
            "compliance_open": len(flags),
        },
        "ctc": _pack(packages),
        "stipend_monthly": _pack(stipends),
        "stipend_other_count": other_stipends,
        "by_course": by_course,
        "by_batch": by_batch,
        "by_company": by_company,
        "attention": attention[:20],
    }


def _attention(student: StudentSnap, kind: str, message: str) -> dict:
    return {
        "student_id": student.id,
        "student_name": student.full_name,
        "placement_id": student.placement_id,
        "kind": kind,
        "message": message,
    }
