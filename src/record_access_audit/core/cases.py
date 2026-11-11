"""Gathering flags into cases: one per staff member and patient, or for high
volume, one per staff member and day."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from record_access_audit.core.rules import Flag, RuleCode


@dataclass(frozen=True, order=True)
class CaseKey:
    staff: str
    patient: str | None  # None for a high-volume day
    day: date | None  # set only for a high-volume day


def key(f: Flag) -> CaseKey:
    if f.code is RuleCode.HIGH_VOLUME:
        return CaseKey(f.staff, None, f.day)
    return CaseKey(f.staff, f.patient, None)


def group(flags: list[Flag]) -> dict[CaseKey, set[RuleCode]]:
    """Each case's rules."""
    cases: dict[CaseKey, set[RuleCode]] = defaultdict(set)
    for f in flags:
        cases[key(f)].add(f.code)
    return dict(cases)
