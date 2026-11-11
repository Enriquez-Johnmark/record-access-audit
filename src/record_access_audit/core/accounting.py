"""Accounting for accesses (B1): an access is accounted for when the clinic's
own data gives the staff member a reason to be in that chart."""

from collections import defaultdict
from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from record_access_audit.core.records import (
    CLINIC_TIME_ZONE,
    Appointment,
    CareTeamMember,
    Clinic,
    Encounter,
    Role,
)
from record_access_audit.core.rules import RuleSet

TZ = ZoneInfo(CLINIC_TIME_ZONE)


class Reason(StrEnum):
    CARE_TEAM = "on the patient's care team"
    ENCOUNTER = "took part in a visit with the patient that day or the day before or after"
    APPOINTMENT = "has an appointment with the patient that day"
    FRONT_DESK_BOOKING = "front desk: the patient has an appointment within 14 days"
    BILLING_VISIT = "billing: the patient had a visit in the 90 days before"


class Index:
    """The clinic's care, by patient, for quick lookups."""

    def __init__(self, clinic: Clinic, rules: RuleSet) -> None:
        self.rules = rules
        self.roles = {s.id: s.role for s in clinic.staff}
        self.care: dict[str, list[CareTeamMember]] = defaultdict(list)
        self.visits: dict[str, list[Encounter]] = defaultdict(list)
        self.bookings: dict[str, list[Appointment]] = defaultdict(list)
        for member in clinic.care_teams:
            self.care[member.patient].append(member)
        for encounter in clinic.encounters:
            self.visits[encounter.patient].append(encounter)
        for appointment in clinic.appointments:
            self.bookings[appointment.patient].append(appointment)


def _day(at: datetime) -> int:
    return at.astimezone(TZ).date().toordinal()


def reasons(index: Index, staff: str, patient: str, at: datetime) -> list[Reason]:
    """Why the clinic's data accounts for `staff` opening `patient`'s chart at `at`; empty if nothing does."""
    rules = index.rules
    found: list[Reason] = []
    if any(m.staff == staff and m.start <= at and (m.end is None or at < m.end) for m in index.care[patient]):
        found.append(Reason.CARE_TEAM)
    today = _day(at)
    if any(
        staff in e.staff and abs(_day(e.start) - today) <= rules.encounter_days for e in index.visits[patient]
    ):
        found.append(Reason.ENCOUNTER)
    if any(a.staff == staff and _day(a.start) == today for a in index.bookings[patient]):
        found.append(Reason.APPOINTMENT)
    role = index.roles.get(staff)
    if role is Role.FRONT_DESK and any(
        abs(_day(a.start) - today) <= rules.front_desk_days for a in index.bookings[patient]
    ):
        found.append(Reason.FRONT_DESK_BOOKING)
    if role is Role.BILLING and any(
        timedelta(0) < at - e.end <= timedelta(days=rules.billing_days) for e in index.visits[patient]
    ):
        found.append(Reason.BILLING_VISIT)
    return found


def last_care_ended(index: Index, staff: str, patient: str, at: datetime) -> datetime | None:
    """When the staff member's most recent care of the patient before `at`
    ended: a care-team membership, a visit or an appointment; None if never."""
    ends = [m.end for m in index.care[patient] if m.staff == staff and m.end is not None and m.end <= at]
    ends += [e.end for e in index.visits[patient] if staff in e.staff and e.end <= at]
    ends += [a.end for a in index.bookings[patient] if a.staff == staff and a.end <= at]
    return max(ends, default=None)
