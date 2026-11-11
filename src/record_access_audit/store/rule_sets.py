"""The rule-set versions: each change inserts a new version with all its
thresholds and weights; no version is ever edited."""

from dataclasses import asdict
from typing import Any, cast

from psycopg.types.json import Jsonb

from record_access_audit.clock import Clock
from record_access_audit.core.records import Role
from record_access_audit.core.rules import DEFAULT_RULES, RuleCode, RuleSet
from record_access_audit.store.audit import SYSTEM, record
from record_access_audit.store.db import Db, transaction


def _settings(rules: RuleSet) -> dict[str, Any]:
    settings = asdict(rules)
    del settings["version"]
    settings["weights"] = {code.value: weight for code, weight in rules.weights.items()}
    settings["roles_no_charts"] = sorted(role.name for role in rules.roles_no_charts)
    return settings


def _rules(version: int, settings: dict[str, Any]) -> RuleSet:
    return RuleSet(
        version=version,
        weights={RuleCode(code): int(weight) for code, weight in settings["weights"].items()},
        roles_no_charts=frozenset(Role[name] for name in settings["roles_no_charts"]),
        encounter_days=int(settings["encounter_days"]),
        front_desk_days=int(settings["front_desk_days"]),
        billing_days=int(settings["billing_days"]),
        after_care_days=int(settings["after_care_days"]),
        shift_grace_minutes=int(settings["shift_grace_minutes"]),
        high_volume_charts=int(settings["high_volume_charts"]),
    )


def current(db: Db, clock: Clock) -> RuleSet:
    """The newest rule-set version; the clinic's default becomes version 1 the first time."""
    row = db.execute(
        "select version, settings from rule_set_versions order by version desc limit 1"
    ).fetchone()
    if row is not None:
        return _rules(int(cast(int, row["version"])), cast(dict[str, Any], row["settings"]))
    install_default(db, clock)
    return current(db, clock)


def install_default(db: Db, clock: Clock) -> None:
    """Makes the clinic's default rules version 1, recorded once, if there is no version yet."""
    with transaction(db):
        inserted = db.execute(
            "insert into rule_set_versions (version, settings, created_at, created_by)"
            " values (1, %s, %s, %s) on conflict do nothing returning version",
            (Jsonb(_settings(DEFAULT_RULES)), clock.now(), SYSTEM),
        ).fetchone()
        if inserted is not None:
            record(
                db,
                at=clock.now(),
                actor=SYSTEM,
                action="rule_set.created",
                subject_type="rule_set",
                subject_id="1",
                details=_settings(DEFAULT_RULES),
            )


class RuleSetError(ValueError):
    pass


THRESHOLDS = {
    "encounter_days": (0, 30),
    "front_desk_days": (0, 90),
    "billing_days": (1, 365),
    "after_care_days": (1, 3650),
    "shift_grace_minutes": (0, 720),
    "high_volume_charts": (1, 10_000),
}


def check(rules: RuleSet) -> None:
    """Refuses a rule set the rules can't run with."""
    if set(rules.weights) != set(RuleCode):
        raise RuleSetError("a rule set needs a weight for every rule")
    for code, weight in rules.weights.items():
        if not 1 <= weight <= 20:
            raise RuleSetError(f"{code.value}'s weight must be between 1 and 20, not {weight}")
    for name, (low, high) in THRESHOLDS.items():
        value = getattr(rules, name)
        if not low <= value <= high:
            raise RuleSetError(f"{name} must be between {low} and {high}, not {value}")


def add_version(db: Db, clock: Clock, actor: str, rules: RuleSet) -> RuleSet:
    """Saves `rules` as the next version; returns it with its number."""
    check(rules)
    with transaction(db):
        db.execute("lock table rule_set_versions in exclusive mode")
        current(db, clock)
        row = db.execute("select max(version) as v from rule_set_versions").fetchone()
        version = int(cast(int, cast(dict[str, Any], row)["v"])) + 1
        settings = _settings(rules)
        db.execute(
            "insert into rule_set_versions (version, settings, created_at, created_by)"
            " values (%s, %s, %s, %s)",
            (version, Jsonb(settings), clock.now(), actor),
        )
        record(
            db,
            at=clock.now(),
            actor=actor,
            action="rule_set.changed",
            subject_type="rule_set",
            subject_id=str(version),
            details=settings,
        )
    return _rules(version, settings)
