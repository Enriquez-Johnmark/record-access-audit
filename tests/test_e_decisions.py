from datetime import timedelta

import pytest

from record_access_audit.audit_run import run_rules
from record_access_audit.decisions import DecisionError, case_decisions, decide, reminder_for
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from record_access_audit.store.queue import open_cases
from tests.support.people import officer_and_admin
from tests.support.stored import stored

FACTS = generate().clinic.facts
REASON = "Covering a colleague's visit; the schedule confirms it."


def test_e1_only_the_privacy_officer_can_decide_a_case(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, admin = officer_and_admin(db)
    case = open_cases(db, clock)[0].id
    with pytest.raises(DecisionError, match="only the privacy officer"):
        decide(db, clock, admin, case, "appropriate", REASON)
    assert case_decisions(db, case) == []
    decide(db, clock, officer, case, "appropriate", REASON)
    assert [d.outcome for d in case_decisions(db, case)] == ["appropriate"]


def test_e2_a_decision_is_one_of_three_outcomes_with_a_reason_of_ten_characters_or_more(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, _ = officer_and_admin(db)
    case = open_cases(db, clock)[0].id
    with pytest.raises(DecisionError, match="one of"):
        decide(db, clock, officer, case, "violation", REASON)
    with pytest.raises(DecisionError, match="at least 10 characters"):
        decide(db, clock, officer, case, "follow-up", "   ok      ")
    with pytest.raises(DecisionError, match="no such case"):
        decide(db, clock, officer, 999_999, "follow-up", REASON)
    for outcome in ("appropriate", "follow-up", "possible breach"):
        decide(db, clock, officer, case, outcome, REASON)
    assert [d.outcome for d in case_decisions(db, case)] == ["appropriate", "follow-up", "possible breach"]


def test_e3_a_later_decision_adds_to_the_history_and_never_replaces_one(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, _ = officer_and_admin(db)
    case = open_cases(db, clock)[0].id
    decide(db, clock, officer, case, "follow-up", "Asking the nurse about the look.")
    clock.at += timedelta(days=2)
    decide(db, clock, officer, case, "appropriate", "The nurse was covering a shift; confirmed.")
    history = case_decisions(db, case)
    assert [(d.outcome, d.decided_by) for d in history] == [
        ("follow-up", "privacy@clinic.example.test"),
        ("appropriate", "privacy@clinic.example.test"),
    ]
    assert history[0].decided_at < history[1].decided_at
    with pytest.raises(Exception, match="append-only"):
        db.execute("update decisions set outcome = 'appropriate'")


def test_e4_a_possible_breach_shows_a_60_day_reminder_labelled_as_not_legal_advice(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, _ = officer_and_admin(db)
    case = open_cases(db, clock)[0].id
    assert reminder_for(case_decisions(db, case)) is None
    decide(db, clock, officer, case, "possible breach", "Same address, no care; needs a risk assessment.")
    reminder = reminder_for(case_decisions(db, case))
    assert reminder is not None
    assert reminder.date == (clock.now() + timedelta(days=60)).date()
    assert reminder.text == (
        "Reminder only, not legal advice: HIPAA allows at most 60 days from discovery to notify."
    )
