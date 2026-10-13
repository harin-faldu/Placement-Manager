import copy
from datetime import date

from app.domain.catalog import DEFAULT_CONFIG, DriveSnap, OfferSnap, StudentSnap
from app.domain.policy import acceptance_window, category_for, evaluate, further_paths, placement_status_of


def config():
    return copy.deepcopy(DEFAULT_CONFIG)


def student(**kwargs) -> StudentSnap:
    data = dict(
        id="s",
        placement_id="NFSU-2026-100",
        full_name="Test Student",
        course="MTECH_CS",
        batch="2026",
        registration_status="registered",
        eligibility_status="eligible",
        cgpa=8.0,
        exclusion_drives_remaining=0,
        absence_review="clear",
        archived=False,
    )
    data.update(kwargs)
    return StudentSnap(**data)


def offer(**kwargs) -> OfferSnap:
    data = dict(
        id="o",
        student_id="s",
        company_id="company-a",
        company_name="Example",
        offer_type="F",
        ctc_lpa=8,
        stipend_amount=None,
        stipend_period=None,
        acceptance_status="accepted",
        joining_status="pending",
        ppo_status="na",
        voided=False,
    )
    data.update(kwargs)
    return OfferSnap(**data)


def drive(**kwargs) -> DriveSnap:
    data = dict(company_id="company-b", offer_type="F", ctc_lpa=20, courses=["MTECH_CS"], min_cgpa=None)
    data.update(kwargs)
    return DriveSnap(**data)


def codes(result):
    return {check.code: check.status for check in result.checks}


def test_category_boundaries():
    rules = config()
    assert category_for(16, rules) == "A+"
    assert category_for(15.99, rules) == "A"
    assert category_for(10, rules) == "A"
    assert category_for(9.99, rules) == "B"
    assert category_for(6, rules) == "B"
    assert category_for(5.99, rules) == "C"


def test_acceptance_window_uses_the_earlier_timeline():
    deadline, window = acceptance_window(date(2026, 10, 13), 48, 24)
    assert window == 24
    short, short_window = acceptance_window(date(2026, 10, 13), 6, 24)
    assert short_window == 6
    assert short < deadline


def test_unplaced_student_can_take_a_first_offer():
    result = evaluate(student(), [], drive(ctc_lpa=4.5), config())
    assert result.verdict == "allow"


def test_registration_and_eligibility_block():
    assert evaluate(student(registration_status="not_registered"), [], drive(), config()).verdict == "block"
    assert evaluate(student(registration_status="deregistered"), [], drive(), config()).verdict == "block"
    assert evaluate(student(eligibility_status="ineligible"), [], drive(), config()).verdict == "block"
    pending = evaluate(student(eligibility_status="pending_verification"), [], drive(), config())
    assert pending.verdict == "review"
    assert codes(pending)["eligibility"] == "review"


def test_archived_record_is_blocked():
    result = evaluate(student(archived=True), [], drive(), config())
    assert result.verdict == "block"
    assert result.checks[0].code == "record"


def test_a_plus_selection_ends_the_process():
    held = offer(ctc_lpa=18, company_id="company-a")
    result = evaluate(student(), [held], drive(offer_type="I", ctc_lpa=None), config())
    assert result.verdict == "block"
    assert codes(result)["a_plus"] == "fail"


def test_fte_lock_is_stricter_than_a_category_switch():
    held = offer(ctc_lpa=12, company_id="company-a")
    result = evaluate(student(), [held], drive(offer_type="F", ctc_lpa=20), config())
    assert result.verdict == "block"
    assert codes(result)["fte_lock"] == "fail"
    assert codes(result)["category"] == "pass"


def test_internship_remains_open_after_fte():
    held = offer(ctc_lpa=12, offer_type="F")
    result = evaluate(student(), [held], drive(offer_type="I", ctc_lpa=None), config())
    assert result.verdict == "allow"


def test_second_internship_is_blocked():
    held = offer(offer_type="I", ctc_lpa=None, stipend_amount=20000, stipend_period="monthly")
    result = evaluate(student(), [held], drive(offer_type="I", ctc_lpa=None), config())
    assert result.verdict == "block"
    assert codes(result)["internship_lock"] == "fail"


def test_internship_can_still_lead_to_fte():
    held = offer(offer_type="I", ctc_lpa=None, stipend_amount=20000, stipend_period="monthly")
    result = evaluate(student(), [held], drive(offer_type="F", ctc_lpa=5), config())
    assert result.verdict == "allow"


def test_category_b_multiplier_and_if_review():
    held = offer(ctc_lpa=8)
    below = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=10), config())
    assert codes(below)["category"] == "fail"
    assert below.verdict == "block"
    meets = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=12), config())
    assert codes(meets)["category"] == "pass"
    assert codes(meets)["if_after_fte"] == "review"
    assert meets.verdict == "review"


def test_category_a_if_must_be_a_plus():
    held = offer(ctc_lpa=12)
    blocked = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=15), config())
    assert codes(blocked)["category"] == "fail"
    allowed = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=18), config())
    assert codes(allowed)["category"] == "pass"
    assert allowed.verdict == "review"


def test_category_c_moves_only_upward():
    held = offer(ctc_lpa=4.5)
    stay = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=5), config())
    assert codes(stay)["category"] == "fail"
    move = evaluate(student(), [held], drive(offer_type="IF", ctc_lpa=7), config())
    assert codes(move)["category"] == "pass"


def test_if_selection_blocks_another_organisation():
    held = offer(offer_type="IF", ctc_lpa=22, company_id="company-a")
    result = evaluate(student(), [held], drive(company_id="company-b", offer_type="I", ctc_lpa=None), config())
    assert result.verdict == "block"
    assert codes(result)["if_lock"] == "fail"


def test_absence_exclusion_and_emergency_review():
    blocked = evaluate(student(exclusion_drives_remaining=3), [], drive(), config())
    assert codes(blocked)["absence"] == "fail"
    review = evaluate(student(absence_review="pending"), [], drive(), config())
    assert review.verdict == "review"


def test_company_cutoff_and_programme():
    assert evaluate(student(cgpa=6.5), [], drive(min_cgpa=7), config()).verdict == "block"
    assert codes(evaluate(student(cgpa=None), [], drive(min_cgpa=7), config()))["academics"] == "review"
    assert evaluate(student(course="MSC_DFIS"), [], drive(courses=["MTECH_CS"]), config()).verdict == "block"


def test_further_paths_follow_the_stricter_rule():
    rules = config()
    assert further_paths(student(), [], rules)["allow"] == ["Internship", "FTE", "Internship + PPO/FTE"]
    a_plus = further_paths(student(), [offer(ctc_lpa=18)], rules)
    assert a_plus["allow"] == []
    after_fte = further_paths(student(), [offer(ctc_lpa=8)], rules)
    assert after_fte["allow"] == ["Internship"]
    assert "Internship + PPO/FTE" in after_fte["review"]


def test_placement_status_counts_a_student_once():
    assert placement_status_of([]) == "unplaced"
    assert placement_status_of([offer(offer_type="I", ctc_lpa=None)]) == "internship_only"
    assert placement_status_of([offer(offer_type="F")]) == "fte_only"
    both = [
        offer(id="1", offer_type="I", ctc_lpa=None),
        offer(id="2", offer_type="F", ctc_lpa=10),
    ]
    assert placement_status_of(both) == "internship_ppo_fte"


def test_category_override_is_explicit_configuration():
    rules = config()
    rules["category_can_override_fte_lock"] = True
    held = offer(ctc_lpa=8)
    result = evaluate(student(), [held], drive(offer_type="F", ctc_lpa=20), rules)
    assert result.verdict == "allow"
    assert codes(result)["fte_lock"] == "pass"
