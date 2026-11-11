"""A tiny made-up clinic for unit tests: four staff, three patients, and
whatever care and accesses a test adds."""

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from record_access_audit.core.records import (
    Access,
    AccessKind,
    Address,
    Appointment,
    CareTeamMember,
    Clinic,
    ClinicFacts,
    Department,
    Encounter,
    Patient,
    Role,
    Section,
    Shift,
    Staff,
)

TZ = ZoneInfo("America/Chicago")
DAY = date(2026, 10, 21)


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


DOCTOR = Staff(
    "S-001",
    "Avery",
    "Testwood",
    Role.PHYSICIAN,
    Department.FAMILY_MEDICINE,
    Address("1 Staff Way", "Example City", "00010"),
)
DESK = Staff(
    "S-002",
    "Blair",
    "Deskton",
    Role.FRONT_DESK,
    Department.ADMINISTRATION,
    Address("2 Staff Way", "Example City", "00010"),
)
CLERK = Staff(
    "S-003",
    "Casey",
    "Billings",
    Role.BILLING,
    Department.ADMINISTRATION,
    Address("3 Staff Way", "Example City", "00010"),
)
GUARD = Staff(
    "S-004",
    "Drew",
    "Gatesby",
    Role.SECURITY,
    Department.ADMINISTRATION,
    Address("4 Staff Way", "Example City", "00010"),
)

ANA = Patient(
    "P-001", "Ana", "Brookfield", date(1980, 1, 2), Address("10 Patient Road", "Example City", "00020"), None
)
BEN = Patient(
    "P-002", "Ben", "Testwood", date(1975, 3, 4), Address("1 Staff Way", "Example City", "00010"), None
)
STAFF_RECORD = Patient("P-003", "Blair", "Deskton", date(1990, 5, 6), DESK.address, None)

OFFICE = Shift(time(8), time(17))


def clinic(
    *,
    care_teams: tuple[CareTeamMember, ...] = (),
    encounters: tuple[Encounter, ...] = (),
    appointments: tuple[Appointment, ...] = (),
    accesses: tuple[Access, ...] = (),
    patients: tuple[Patient, ...] = (ANA, BEN, STAFF_RECORD),
    vips: frozenset[str] = frozenset(),
) -> Clinic:
    return Clinic(
        staff=(DOCTOR, DESK, CLERK, GUARD),
        patients=patients,
        care_teams=care_teams,
        encounters=encounters,
        appointments=appointments,
        accesses=accesses,
        facts=ClinicFacts(
            shifts={s.id: OFFICE for s in (DOCTOR, DESK, CLERK, GUARD)},
            staff_records={DESK.id: STAFF_RECORD.id},
            vips=vips,
        ),
    )


def opened(staff: Staff, patient: Patient, when: datetime, number: int = 1) -> Access:
    return Access(
        f"A-{number:05d}", staff.id, when, AccessKind.CHART, (patient.id,), Section.SUMMARY, 60, "WS-1"
    )


def searched(staff: Staff, patients: list[Patient], when: datetime, number: int = 1) -> Access:
    return Access(
        f"A-{number:05d}", staff.id, when, AccessKind.SEARCH, tuple(p.id for p in patients), None, 0, "WS-1"
    )


def visit(patient: Patient, staff: Staff, start: datetime, number: int = 1) -> Encounter:
    return Encounter(f"E-{number:04d}", patient.id, (staff.id,), start, start + timedelta(minutes=45))


def booking(patient: Patient, staff: Staff, start: datetime, number: int = 1) -> Appointment:
    return Appointment(f"AP-{number:04d}", patient.id, staff.id, start, start + timedelta(minutes=30))


def member(patient: Patient, staff: Staff, start: datetime, end: datetime | None = None) -> CareTeamMember:
    return CareTeamMember(patient.id, staff.id, start, end)


def dead(patient: Patient, when: datetime) -> Patient:
    return replace(patient, deceased_at=when)
