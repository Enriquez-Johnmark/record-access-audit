"""The clinic's eleven rules (B2), run over every access under one rule-set
version. Code decides what is flagged; a model never does. A search-list hit
is never flagged (B3): only charts opened are."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from record_access_audit.core.records import CLINIC_TIME_ZONE, AccessKind, Clinic, Patient, Role, Shift, Staff

if TYPE_CHECKING:
    from record_access_audit.core.accounting import Index

TZ = ZoneInfo(CLINIC_TIME_ZONE)


class RuleCode(StrEnum):
    OWN_RECORD = "OWN_RECORD"
    ROLE_NO_CHARTS = "ROLE_NO_CHARTS"
    NO_RELATIONSHIP = "NO_RELATIONSHIP"
    SAME_LAST_NAME = "SAME_LAST_NAME"
    SAME_ADDRESS = "SAME_ADDRESS"
    COWORKER = "COWORKER"
    VIP = "VIP"
    DECEASED = "DECEASED"
    AFTER_CARE_ENDED = "AFTER_CARE_ENDED"
    OUTSIDE_SHIFT = "OUTSIDE_SHIFT"
    HIGH_VOLUME = "HIGH_VOLUME"


# The rules that look only at accesses the clinic's data doesn't account for.
ONLY_UNACCOUNTED = frozenset(
    {
        RuleCode.NO_RELATIONSHIP,
        RuleCode.SAME_LAST_NAME,
        RuleCode.SAME_ADDRESS,
        RuleCode.COWORKER,
        RuleCode.VIP,
        RuleCode.DECEASED,
        RuleCode.AFTER_CARE_ENDED,
        RuleCode.OUTSIDE_SHIFT,
    }
)

DESCRIPTIONS = {
    RuleCode.OWN_RECORD: "The staff member opened their own record.",
    RuleCode.ROLE_NO_CHARTS: "The staff member's role never reads charts.",
    RuleCode.NO_RELATIONSHIP: "No care team, visit, appointment or the role's work accounts for the look.",
    RuleCode.SAME_LAST_NAME: "The patient shares the staff member's last name.",
    RuleCode.SAME_ADDRESS: "The patient lives at the staff member's home address.",
    RuleCode.COWORKER: "The patient is another staff member.",
    RuleCode.VIP: "The patient is on the clinic's VIP list.",
    RuleCode.DECEASED: "The patient had died before the look.",
    RuleCode.AFTER_CARE_ENDED: "The staff member's care of the patient ended long before the look.",
    RuleCode.OUTSIDE_SHIFT: "The chart was opened well outside the staff member's shift.",
    RuleCode.HIGH_VOLUME: "The staff member opened an unusual number of charts that day.",
}

DEFAULT_WEIGHTS: dict[RuleCode, int] = {
    RuleCode.OWN_RECORD: 3,
    RuleCode.ROLE_NO_CHARTS: 3,
    RuleCode.NO_RELATIONSHIP: 1,
    RuleCode.SAME_LAST_NAME: 2,
    RuleCode.SAME_ADDRESS: 3,
    RuleCode.COWORKER: 2,
    RuleCode.VIP: 2,
    RuleCode.DECEASED: 2,
    RuleCode.AFTER_CARE_ENDED: 1,
    RuleCode.OUTSIDE_SHIFT: 1,
    RuleCode.HIGH_VOLUME: 2,
}


@dataclass(frozen=True)
class RuleSet:
    """One version of the clinic's rules: its thresholds and weights."""

    version: int = 1
    weights: dict[RuleCode, int] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    roles_no_charts: frozenset[Role] = frozenset({Role.IT, Role.SECURITY})
    encounter_days: int = 1
    front_desk_days: int = 14
    billing_days: int = 90
    after_care_days: int = 30
    shift_grace_minutes: int = 60
    high_volume_charts: int = 60


DEFAULT_RULES = RuleSet()


@dataclass(frozen=True)
class Flag:
    """One rule firing on one access (for HIGH_VOLUME, on each chart of the day)."""

    access: str
    staff: str
    patient: str | None  # None for HIGH_VOLUME, which is about the staff member's day
    day: date
    code: RuleCode
    version: int


def _minutes_outside(shift: Shift, at: datetime) -> float:
    """How far `at` falls outside `shift`, in minutes (0 inside it)."""
    local = at.astimezone(TZ)
    clock = local.hour * 60 + local.minute + local.second / 60
    start = shift.start.hour * 60 + shift.start.minute
    end = shift.end.hour * 60 + shift.end.minute
    inside = start <= clock < end if start < end else clock >= start or clock < end
    if inside:
        return 0
    day = 24 * 60
    return min((start - clock) % day, (clock - end) % day)


def _same_address(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def _codes(
    clinic: Clinic,
    rules: RuleSet,
    index: "Index",
    person: Staff,
    patient: Patient,
    owners: dict[str, str],
    at: datetime,
) -> list[RuleCode]:
    """The rules that fire on `person` opening `patient`'s chart at `at`."""
    from record_access_audit.core.accounting import last_care_ended, reasons

    if clinic.facts.staff_records.get(person.id) == patient.id:
        return [RuleCode.OWN_RECORD]
    fired: list[RuleCode] = []
    if person.role in rules.roles_no_charts:
        fired.append(RuleCode.ROLE_NO_CHARTS)
    if reasons(index, person.id, patient.id, at):
        return fired
    fired.append(RuleCode.NO_RELATIONSHIP)
    if patient.family.lower() == person.family.lower():
        fired.append(RuleCode.SAME_LAST_NAME)
    if _same_address(patient.address.line, person.address.line) and (
        patient.address.postal_code == person.address.postal_code
    ):
        fired.append(RuleCode.SAME_ADDRESS)
    if patient.id in owners:
        fired.append(RuleCode.COWORKER)
    if patient.id in clinic.facts.vips:
        fired.append(RuleCode.VIP)
    if patient.deceased_at is not None and patient.deceased_at < at:
        fired.append(RuleCode.DECEASED)
    ended = last_care_ended(index, person.id, patient.id, at)
    if ended is not None and at - ended > timedelta(days=rules.after_care_days):
        fired.append(RuleCode.AFTER_CARE_ENDED)
    shift = clinic.facts.shifts.get(person.id)
    if shift is not None and _minutes_outside(shift, at) > rules.shift_grace_minutes:
        fired.append(RuleCode.OUTSIDE_SHIFT)
    return fired


def flag(clinic: Clinic, rules: RuleSet) -> list[Flag]:
    # Imported here: accounting reads the rule set's thresholds.
    from record_access_audit.core.accounting import Index

    index = Index(clinic, rules)
    staff = {s.id: s for s in clinic.staff}
    patients = {p.id: p for p in clinic.patients}
    owners = {record: owner for owner, record in clinic.facts.staff_records.items()}
    flags: list[Flag] = []
    charts_by_day: dict[tuple[str, date], list[tuple[str, str]]] = defaultdict(list)

    for access in clinic.accesses:
        if access.kind is not AccessKind.CHART:
            continue
        person = staff[access.staff]
        patient = patients[access.patients[0]]
        day = access.at.astimezone(TZ).date()
        charts_by_day[(person.id, day)].append((access.id, patient.id))
        flags.extend(
            Flag(access.id, person.id, patient.id, day, code, rules.version)
            for code in _codes(clinic, rules, index, person, patient, owners, access.at)
        )

    for (staff_id, day), charts in charts_by_day.items():
        if len({patient for _, patient in charts}) > rules.high_volume_charts:
            flags.extend(
                Flag(access_id, staff_id, None, day, RuleCode.HIGH_VOLUME, rules.version)
                for access_id, _ in charts
            )
    return flags
