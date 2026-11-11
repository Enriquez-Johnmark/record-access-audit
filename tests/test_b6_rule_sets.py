from dataclasses import replace

import pytest

from record_access_audit.core.rules import DEFAULT_RULES, RuleCode
from record_access_audit.store.db import Db
from record_access_audit.store.rule_sets import RuleSetError, add_version, current, install_default
from tests.support.stored import stored

OFFICER = "privacy@clinic.example.test"


def created(db: Db) -> int:
    row = db.execute("select count(*) as n from audit_events where action = 'rule_set.created'").fetchone()
    assert row is not None
    return int(row["n"])  # type: ignore[arg-type]


def test_b6_version_1_is_recorded_as_created_once_even_when_two_install_it(db: Db) -> None:
    clock = stored(db)
    install_default(db, clock)
    install_default(db, clock)
    current(db, clock)
    assert created(db) == 1


def test_b6_a_rule_set_missing_a_weight_or_with_a_bad_threshold_is_refused(db: Db) -> None:
    clock = stored(db)
    missing = {code: w for code, w in DEFAULT_RULES.weights.items() if code is not RuleCode.HIGH_VOLUME}
    for bad, problem in [
        (replace(DEFAULT_RULES, weights=missing), "a weight for every rule"),
        (replace(DEFAULT_RULES, weights={**DEFAULT_RULES.weights, RuleCode.VIP: 0}), "between 1 and 20"),
        (replace(DEFAULT_RULES, high_volume_charts=-1), "high_volume_charts"),
        (replace(DEFAULT_RULES, after_care_days=0), "after_care_days"),
    ]:
        with pytest.raises(RuleSetError, match=problem):
            add_version(db, clock, OFFICER, bad)
    assert current(db, clock).version == 1


def test_b6_only_the_privacy_officer_changes_the_rules_and_each_change_is_a_new_version(db: Db) -> None:
    from record_access_audit.store.rule_sets import change_rules
    from tests.support.people import officer_and_admin

    clock = stored(db)
    officer, admin = officer_and_admin(db)
    with pytest.raises(RuleSetError, match="only the privacy officer"):
        change_rules(db, clock, admin, replace(DEFAULT_RULES, high_volume_charts=50))
    changed = change_rules(db, clock, officer, replace(DEFAULT_RULES, high_volume_charts=50))
    assert (changed.version, changed.high_volume_charts) == (2, 50)
    assert current(db, clock) == changed
    row = db.execute("select created_by from rule_set_versions where version = 2").fetchone()
    assert row == {"created_by": OFFICER}
