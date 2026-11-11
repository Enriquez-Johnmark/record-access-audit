"""The clinic's records as typed values: who the staff and patients are, the
care that links them, and every access in the log. The FHIR reader produces
these; the rules read only these."""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

# The clinic's time zone: shifts and days are counted in it.
CLINIC_TIME_ZONE = "America/Chicago"


class Role(StrEnum):
    PHYSICIAN = "physician"
    NURSE = "nurse"
    MEDICAL_ASSISTANT = "medical assistant"
    FRONT_DESK = "front desk"
    BILLING = "billing"
    LAB_TECHNICIAN = "lab technician"
    IT = "IT"
    SECURITY = "security"


class Department(StrEnum):
    FAMILY_MEDICINE = "Family Medicine"
    PEDIATRICS = "Pediatrics"
    URGENT_CARE = "Urgent Care"
    LAB = "Laboratory"
    ADMINISTRATION = "Administration"


class Section(StrEnum):
    """Which part of a chart was opened, by category only."""

    SUMMARY = "summary"
    RESULTS = "results"
    NOTES = "notes"
    MEDICINES = "medicines"
    BILLING = "billing"


class AccessKind(StrEnum):
    CHART = "chart opened"
    SEARCH = "search list"


@dataclass(frozen=True)
class Address:
    line: str
    city: str
    postal_code: str


@dataclass(frozen=True)
class Shift:
    """Working hours in the clinic's time zone; `end` before `start` runs past midnight."""

    start: time
    end: time


@dataclass(frozen=True)
class Staff:
    id: str  # S-001
    given: str
    family: str
    role: Role
    department: Department
    address: Address


@dataclass(frozen=True)
class Patient:
    id: str  # P-001
    given: str
    family: str
    birth_date: date
    address: Address
    deceased_at: datetime | None


@dataclass(frozen=True)
class CareTeamMember:
    patient: str
    staff: str
    start: datetime
    end: datetime | None


@dataclass(frozen=True)
class Encounter:
    id: str
    patient: str
    staff: tuple[str, ...]
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Appointment:
    id: str
    patient: str
    staff: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Access:
    """One entry in the access log: a chart opened (one patient) or a search
    list (every patient it showed)."""

    id: str
    staff: str
    at: datetime
    kind: AccessKind
    patients: tuple[str, ...]
    section: Section | None
    seconds: int
    workstation: str


@dataclass(frozen=True)
class ClinicFacts:
    """What the clinic knows that has no clean FHIR home."""

    shifts: dict[str, Shift]  # by staff ID
    staff_records: dict[str, str]  # staff ID -> that staff member's own patient ID
    vips: frozenset[str]  # patient IDs


@dataclass(frozen=True)
class Clinic:
    staff: tuple[Staff, ...]
    patients: tuple[Patient, ...]
    care_teams: tuple[CareTeamMember, ...]
    encounters: tuple[Encounter, ...]
    appointments: tuple[Appointment, ...]
    accesses: tuple[Access, ...]
    facts: ClinicFacts
