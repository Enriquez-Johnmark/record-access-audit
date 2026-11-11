import psycopg
import pytest

from record_access_audit.activity import activity, timeline
from record_access_audit.audit_run import run_rules
from record_access_audit.case_view import view_case
from record_access_audit.decisions import decide
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from record_access_audit.store.queue import open_cases
from tests.support.people import officer_and_admin
from tests.support.stored import stored

FACTS = generate().clinic.facts


def test_g1_every_step_is_logged_with_who_and_when(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, _ = officer_and_admin(db)
    case = open_cases(db, clock)[0].id
    view_case(db, clock, officer, FACTS, case)
    decide(db, clock, officer, case, "follow-up", "Asking the staff member about it.")
    steps = [(e.action, e.actor) for e in timeline(db, case)]
    assert steps == [
        ("case.flagged", "system"),
        ("case.viewed", "privacy@clinic.example.test"),
        ("decision.recorded", "privacy@clinic.example.test"),
    ]
    assert all(e.at == clock.now() for e in timeline(db, case))


def test_g2_the_database_refuses_to_change_or_delete_a_log_entry(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    for sql in ["update audit_events set actor = 'x'", "delete from audit_events", "truncate audit_events"]:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            db.execute(sql)  # type: ignore[arg-type]


def test_g3_each_case_has_its_timeline_and_the_whole_log_filters_by_person_and_step(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer, _ = officer_and_admin(db)
    first, second = (row.id for row in open_cases(db, clock)[:2])
    view_case(db, clock, officer, FACTS, first)
    view_case(db, clock, officer, FACTS, second)
    assert [e.subject_id for e in timeline(db, first) if e.action == "case.viewed"] == [str(first)]
    viewed = activity(db, actor="privacy@clinic.example.test", action="case.viewed")
    assert sorted(e.subject_id for e in viewed) == sorted([str(first), str(second)])
    assert {e.action for e in activity(db, actor="system")} >= {"case.flagged", "rules.run"}
    assert activity(db, actor="nobody@example.test") == []
    newest_first = activity(db)
    assert [e.id for e in newest_first] == sorted((e.id for e in newest_first), reverse=True)
