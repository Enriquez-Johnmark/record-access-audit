from dataclasses import replace
from datetime import timedelta
from typing import LiteralString, cast

from record_access_audit.audit_run import fetch_and_run, run_rules
from record_access_audit.clock import FixedClock
from record_access_audit.core.rules import DEFAULT_RULES
from record_access_audit.fhir.client import FhirServer
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from record_access_audit.store.rule_sets import add_version, current
from tests.support.stored import NOW, stored

FACTS = generate().clinic.facts


def count(db: Db, sql: LiteralString) -> int:
    row = db.execute(sql).fetchone()
    assert row is not None
    return int(cast(int, row["n"]))


def test_b4_running_the_rules_again_raises_no_new_flags_or_cases(db: Db) -> None:
    clock = stored(db)
    first = run_rules(db, clock, FACTS)
    assert first.cases == 34
    assert first.flags == count(db, "select count(*) as n from flags")
    second = run_rules(db, clock, FACTS)
    assert (second.flags, second.cases) == (0, 0)


def test_b4_a_new_rule_set_version_flags_under_its_own_number_and_never_rewrites_a_past_flag(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    before = db.execute("select id, access, code, version, case_id from flags order by id").fetchall()
    add_version(db, clock, "privacy@clinic.example.test", replace(DEFAULT_RULES, after_care_days=20))

    again = run_rules(db, clock, FACTS)

    assert again.cases == 0
    assert again.flags == len(before)
    assert (
        db.execute(
            "select id, access, code, version, case_id from flags where version = 1 order by id"
        ).fetchall()
        == before
    )
    assert count(db, "select count(distinct case_id) as n from flags where version = 2") == 34


def test_b4_a_flag_after_a_decision_opens_a_new_case(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    decided = db.execute("select id from cases order by id limit 1").fetchone()
    assert decided is not None
    db.execute(
        "insert into decisions (case_id, outcome, reason, decided_by, decided_at)"
        " values (%s, 'appropriate', %s, %s, %s)",
        (
            decided["id"],
            "Covering a colleague's visit, confirmed.",
            "privacy@clinic.example.test",
            clock.now(),
        ),
    )
    clock.at += timedelta(days=1)
    add_version(db, clock, "privacy@clinic.example.test", replace(DEFAULT_RULES, after_care_days=20))

    again = run_rules(db, clock, FACTS)

    assert again.cases == 1
    row = db.execute(
        "select count(*) as n from flags where case_id = %s and version = 2", (decided["id"],)
    ).fetchone()
    assert row == {"n": 0}


def test_b4_the_first_rule_set_is_the_clinics_default_as_version_1(db: Db) -> None:
    clock = stored(db)
    assert current(db, clock) == DEFAULT_RULES
    assert current(db, clock).version == 1


def test_b4_a_run_from_the_fhir_server_stores_the_log_and_flags_it_once(
    db: Db, loaded_fhir: FhirServer
) -> None:
    clock = FixedClock(NOW)
    first = fetch_and_run(db, clock, loaded_fhir, FACTS)
    assert first.refused == []
    assert first.new_accesses == len(generate().clinic.accesses)
    assert first.run.cases == 34
    again = fetch_and_run(db, clock, loaded_fhir, FACTS)
    assert (again.new_accesses, again.run.flags, again.run.cases) == (0, 0, 0)
