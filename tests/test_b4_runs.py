from dataclasses import replace
from typing import LiteralString, cast

from record_access_audit.audit_run import fetch_and_run, run_rules
from record_access_audit.clock import FixedClock
from record_access_audit.core.rules import DEFAULT_RULES, RuleCode
from record_access_audit.fhir.client import FhirServer
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from record_access_audit.store.rule_sets import add_version, current
from tests.support.stored import NOW, stored

OFFICER = "privacy@clinic.example.test"

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
    add_version(db, clock, OFFICER, replace(DEFAULT_RULES, high_volume_charts=20))

    again = run_rules(db, clock, FACTS)

    assert again.version == 2
    assert again.cases > 0
    assert (
        db.execute(
            "select id, access, code, version, case_id from flags where version = 1 order by id"
        ).fetchall()
        == before
    )
    assert count(db, "select count(*) as n from flags where version = 2 and code <> 'HIGH_VOLUME'") == 0


def decide_all(db: Db, clock: FixedClock) -> None:
    db.execute(
        "insert into decisions (case_id, outcome, reason, decided_by, decided_at)"
        " select id, 'appropriate', 'Reviewed in the test.', %s, %s from cases",
        (OFFICER, clock.now()),
    )


def test_b4_a_new_version_that_finds_nothing_new_reopens_nothing(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    decide_all(db, clock)
    weights = {**DEFAULT_RULES.weights, RuleCode.VIP: 9}
    add_version(db, clock, OFFICER, replace(DEFAULT_RULES, weights=weights, after_care_days=20))

    again = run_rules(db, clock, FACTS)

    assert (again.flags, again.cases) == (0, 0)


def test_b4_a_flag_after_a_decision_opens_a_new_case(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    decided = db.execute(
        "select c.id, f.access from cases c join flags f on f.case_id = c.id"
        " where c.patient is not null order by c.id, f.access limit 1"
    ).fetchone()
    assert decided is not None
    decide_all(db, clock)
    db.execute(
        "insert into accesses (id, staff, at, kind, patients, section, seconds, workstation)"
        " select 'A-99999', staff, at + interval '2 days', kind, patients, section, seconds, workstation"
        " from accesses where id = %s",
        (decided["access"],),
    )

    again = run_rules(db, clock, FACTS)

    assert again.cases == 1
    new_case = db.execute("select distinct case_id, access from flags where access = 'A-99999'").fetchall()
    assert len({row["case_id"] for row in new_case}) == 1
    assert new_case[0]["case_id"] != decided["id"]


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
