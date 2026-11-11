from dataclasses import replace
from datetime import timedelta

from record_access_audit.audit_run import run_rules
from record_access_audit.core.rules import DEFAULT_RULES, RuleCode
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from record_access_audit.store.queue import open_cases
from record_access_audit.store.rule_sets import add_version
from tests.support.stored import stored

FACTS = generate().clinic.facts


def test_b5_the_queue_holds_every_open_case_by_weight_then_age(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    queue = open_cases(db, clock)

    assert len(queue) == 34
    keys = [(-row.score, row.flagged_at, row.first_access_at, row.id) for row in queue]
    assert keys == sorted(keys)
    assert queue[0].score >= 5
    assert queue[-1].score == 1


def test_b5_an_open_case_is_never_hidden_or_closed_however_old(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    clock.at += timedelta(days=400)
    queue = open_cases(db, clock)
    assert len(queue) == 34
    assert all(row.age_days >= 400 for row in queue)


def test_b5_a_decided_case_leaves_the_queue(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    first = open_cases(db, clock)[0]
    db.execute(
        "insert into decisions (case_id, outcome, reason, decided_by, decided_at)"
        " values (%s, 'follow-up', %s, %s, %s)",
        (first.id, "Will ask the staff member about it.", "privacy@clinic.example.test", clock.now()),
    )
    assert [row.id for row in open_cases(db, clock)] == [
        row.id for row in open_cases(db, clock) if row.id != first.id
    ]
    assert first.id not in [row.id for row in open_cases(db, clock)]


def test_b5_the_queue_weighs_cases_by_the_current_rule_set(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    add_version(
        db,
        clock,
        "privacy@clinic.example.test",
        replace(DEFAULT_RULES, weights={**DEFAULT_RULES.weights, RuleCode.VIP: 20}),
    )
    queue = open_cases(db, clock)
    assert all("VIP" in row.codes for row in queue[:4])
    assert queue[0].score == 21
