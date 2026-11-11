"""The numbered facts of a case, built by code from the log and the clinic's
data (A2, C1). This is all the model ever sees: pseudonymous IDs (S-009,
P-286), roles, departments, shifts, times, actions, section categories, the
rules that raised the case and what the clinic's data does and doesn't show.
Never a name, address, date of birth, diagnosis, note, result or medicine."""

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from record_access_audit.core.accounting import Index, last_care_ended, reasons
from record_access_audit.core.cases import CaseKey
from record_access_audit.core.records import CLINIC_TIME_ZONE, Access, AccessKind, Clinic
from record_access_audit.core.rules import DESCRIPTIONS, Flag, RuleCode, RuleSet

TZ = ZoneInfo(CLINIC_TIME_ZONE)
MAX_LOOKS = 10


def _when(at: datetime) -> str:
    return at.astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def _times(n: int) -> str:
    return "1 time" if n == 1 else f"{n} times"


def _rule(code: RuleCode) -> str:
    description = DESCRIPTIONS[code]
    return f"Rule {code.value} raised this case: {description[0].lower()}{description[1:]}"


def case_facts(clinic: Clinic, rules: RuleSet, case: CaseKey, flags: list[Flag]) -> list[str]:
    """The case's facts, in a fixed order; fact 1 is `facts[0]`."""
    staff = next(s for s in clinic.staff if s.id == case.staff)
    shift = clinic.facts.shifts.get(staff.id)
    facts = [
        f"Staff member {staff.id}'s role is {staff.role.value}, in {staff.department.value}"
        + (f"; their shift is {shift.start:%H:%M} to {shift.end:%H:%M}." if shift else ".")
    ]
    accesses = {a.id: a for a in clinic.accesses}
    looks = sorted({accesses[f.access] for f in flags}, key=lambda a: (a.at, a.id))
    codes = sorted({f.code for f in flags}, key=list(RuleCode).index)
    index = Index(clinic, rules)
    if case.patient is None:
        facts += _volume_facts(clinic, index, staff.id, looks)
    else:
        facts += _pair_facts(clinic, index, staff.id, case.patient, looks)
    facts += [_rule(code) for code in codes]
    return facts


def _pair_facts(clinic: Clinic, index: Index, staff: str, patient_id: str, looks: list[Access]) -> list[str]:
    patient = next(p for p in clinic.patients if p.id == patient_id)
    person = next(s for s in clinic.staff if s.id == staff)
    facts: list[str] = []
    if clinic.facts.staff_records.get(staff) == patient_id:
        facts.append(f"Patient {patient_id} is {staff}'s own record.")
    elif patient_id in clinic.facts.staff_records.values():
        facts.append(f"Patient {patient_id} is another staff member's record.")
    if patient_id in clinic.facts.vips:
        facts.append(f"Patient {patient_id} is on the clinic's VIP list.")
    if (
        patient.family.lower() == person.family.lower()
        and clinic.facts.staff_records.get(staff) != patient_id
    ):
        facts.append(f"Patient {patient_id} shares {staff}'s last name.")
    if patient.address == person.address and clinic.facts.staff_records.get(staff) != patient_id:
        facts.append(f"Patient {patient_id} lives at {staff}'s home address.")
    if patient.deceased_at is not None and looks and patient.deceased_at < looks[0].at:
        facts.append(
            f"Patient {patient_id} had died before the first look, on {patient.deceased_at.astimezone(TZ):%Y-%m-%d}."
        )
    for look in looks[:MAX_LOOKS]:
        section = look.section.value if look.section else "summary"
        facts.append(
            f"At {_when(look.at)}, {staff} opened {patient_id}'s chart ({section}) for {look.seconds} seconds."
        )
    if looks:
        span = (
            f"at {_when(looks[0].at)}"
            if len(looks) == 1
            else f"between {_when(looks[0].at)} and {_when(looks[-1].at)}"
        )
        facts.append(f"In all, {staff} opened {patient_id}'s chart {_times(len(looks))}, {span}.")
    searches = [
        a
        for a in clinic.accesses
        if a.staff == staff and a.kind is AccessKind.SEARCH and patient_id in a.patients
    ]
    if searches:
        facts.append(
            f"{patient_id} also appeared in {len(searches)} search list(s) on {staff}'s screen, the first at"
            f" {_when(searches[0].at)}; a search list shows names only, and appearing in one is not opening the chart."
        )
    accounted = [(look, reasons(index, staff, patient_id, look.at)) for look in looks]
    if not any(why for _, why in accounted):
        facts.append(
            "Nothing in the clinic's data accounts for these looks: no care team, visit, appointment or role's work."
        )
    for look, why in accounted:
        if why:
            facts.append(
                f"The clinic's data accounts for the look at {_when(look.at)}: {staff} {why[0].value}."
            )
    if looks:
        ended = last_care_ended(index, staff, patient_id, looks[0].at)
        if ended is not None:
            facts.append(
                f"{staff}'s most recent care of {patient_id} before the first look ended on {ended.astimezone(TZ):%Y-%m-%d}."
            )
        elif not any(why for _, why in accounted):
            facts.append(f"The clinic's data shows no earlier care of {patient_id} by {staff}.")
    return facts


def _volume_facts(clinic: Clinic, index: Index, staff: str, looks: list[Access]) -> list[str]:
    if not looks:
        return []
    day = looks[0].at.astimezone(TZ).date()
    patients = {look.patients[0] for look in looks}
    per_day: dict[object, set[str]] = defaultdict(set)
    for a in clinic.accesses:
        if a.staff == staff and a.kind is AccessKind.CHART:
            per_day[a.at.astimezone(TZ).date()].add(a.patients[0])
    others = [len(p) for d, p in per_day.items() if d != day]
    accounted = sum(1 for look in looks if reasons(index, staff, look.patients[0], look.at))
    facts = [
        f"On {day:%Y-%m-%d}, {staff} opened the charts of {len(patients)} different patients,"
        f" between {looks[0].at.astimezone(TZ):%H:%M} and {looks[-1].at.astimezone(TZ):%H:%M}."
    ]
    if others:
        facts.append(
            f"On the other days in the log, {staff} opened the charts of at most {max(others)} patients a day."
        )
    facts.append(
        f"The clinic's data (care teams, visits, appointments or the role's work) accounts for {accounted}"
        f" of the {len(looks)} chart openings that day."
    )
    return facts
