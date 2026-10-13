from app.domain import DEFAULT_CONFIG, OfferSnap, StudentSnap
from app.stats import summarize


def student(sid, course="MTECH_CS", **kwargs):
    data = dict(
        id=sid,
        placement_id=sid,
        full_name=sid,
        course=course,
        batch="2026",
        registration_status="registered",
        eligibility_status="eligible",
        cgpa=8,
        exclusion_drives_remaining=0,
        absence_review="clear",
        archived=False,
    )
    data.update(kwargs)
    return StudentSnap(**data)


def test_package_stats_ignore_stipends_and_count_people_once():
    students = [student("a"), student("b")]
    offers = [
        OfferSnap("1", "a", "c", "Northstar", "F", 10, None, None, "accepted", "joined", "na", False),
        OfferSnap("2", "a", "c2", "Other", "F", 18, None, None, "accepted", "joined", "na", False),
        OfferSnap("3", "b", "c3", "Fieldnote", "I", None, 20000, "monthly", "accepted", "pending", "na", False),
        OfferSnap("4", "b", "c4", "Voided", "F", 30, None, None, "accepted", "joined", "na", True),
    ]
    report = summarize(students, offers, [], DEFAULT_CONFIG)
    assert report["totals"]["placed"] == 2
    assert report["totals"]["offers"] == 3
    assert report["totals"]["fte_only"] == 1
    assert report["totals"]["internship_only"] == 1
    assert report["ctc"]["highest"] == 18
    assert report["ctc"]["count"] == 1
    assert report["stipend_monthly"]["highest"] == 20000
    assert report["totals"]["placed"] == (
        report["totals"]["internship_only"] + report["totals"]["fte_only"] + report["totals"]["internship_ppo_fte"]
    )
