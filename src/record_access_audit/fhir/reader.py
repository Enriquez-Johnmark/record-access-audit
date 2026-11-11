"""The strict reader (H2): FHIR R4 resources from the clinic's server parsed
into typed records. A resource it can't read is refused with the reason, and
the others are taken in. Nothing from the server is trusted until parsed."""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError

from record_access_audit.core.records import (
    CLINIC_TIME_ZONE,
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
from record_access_audit.fhir.build import DETAIL_SECONDS, DETAIL_SECTION, our_id

TZ = ZoneInfo(CLINIC_TIME_ZONE)


@dataclass(frozen=True)
class Refused:
    resource: str  # e.g. AuditEvent/evc-a00001
    reason: str


@dataclass(frozen=True)
class ReadResult:
    clinic: Clinic
    refused: list[Refused]


class _Strict(BaseModel):
    # FHIR servers add fields (meta.versionId, text...); only what we read is checked.
    model_config = ConfigDict(extra="ignore", frozen=True)


class _Reference(_Strict):
    reference: str


class _HumanName(_Strict):
    family: str
    given: list[str]


class _Address(_Strict):
    line: list[str]
    city: str
    postalCode: str  # noqa: N815 (FHIR's name)


class _Coding(_Strict):
    system: str
    code: str


class _Concept(_Strict):
    coding: list[_Coding]


class _Practitioner(_Strict):
    id: str
    name: list[_HumanName]
    address: list[_Address]


class _PractitionerRole(_Strict):
    practitioner: _Reference
    code: list[_Concept]
    specialty: list[_Concept]


class _Patient(_Strict):
    id: str
    name: list[_HumanName]
    birthDate: date  # noqa: N815
    address: list[_Address]
    deceasedDateTime: datetime | None = None  # noqa: N815


class _Period(_Strict):
    start: datetime
    end: datetime | None = None


class _Participant(_Strict):
    member: _Reference
    period: _Period


class _CareTeam(_Strict):
    subject: _Reference
    participant: list[_Participant]


class _EncounterParticipant(_Strict):
    individual: _Reference


class _Encounter(_Strict):
    id: str
    subject: _Reference
    participant: list[_EncounterParticipant]
    period: _Period


class _AppointmentParticipant(_Strict):
    actor: _Reference


class _Appointment(_Strict):
    id: str
    start: datetime
    end: datetime
    participant: list[_AppointmentParticipant]


class _Detail(_Strict):
    type: str
    valueString: str  # noqa: N815


class _Entity(_Strict):
    what: _Reference
    detail: list[_Detail] = []


class _Network(_Strict):
    address: str


class _Agent(_Strict):
    who: _Reference
    requestor: Literal[True]
    network: _Network


class _AuditEvent(_Strict):
    id: str
    subtype: list[_Coding]
    recorded: datetime
    agent: list[_Agent]
    entity: list[_Entity]


class _UnreadableError(Exception):
    pass


def _local(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise _UnreadableError("a time without a time zone")
    return at.astimezone(TZ)


def _address(address: list[_Address]) -> Address:
    first = address[0]
    return Address(first.line[0], first.city, first.postalCode)


def _code(concepts: list[_Concept], enum: type[Role] | type[Department]) -> Any:
    code = concepts[0].coding[0].code
    try:
        return enum[code]
    except KeyError:
        raise _UnreadableError(f"unknown {enum.__name__.lower()} ({code})") from None


def _target(reference: _Reference, kind: str, known: set[str], what: str) -> str:
    prefix = f"{kind}/"
    if not reference.reference.startswith(prefix):
        raise _UnreadableError(f"expected a {kind} reference ({reference.reference})")
    letter = "S" if kind == "Practitioner" else "P"
    our = our_id(reference.reference.removeprefix(prefix), letter)
    if our not in known:
        raise _UnreadableError(f"names {what} not in the clinic ({reference.reference})")
    return our


def _reason(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}"


def read(resources: dict[str, list[dict[str, Any]]], facts: ClinicFacts) -> ReadResult:
    """Every resource in `resources` (by type) read into the clinic; what can't
    be read is refused with its reason."""
    refused: list[Refused] = []

    def each[T: _Strict](kind: str, model: type[T]) -> list[tuple[dict[str, Any], T]]:
        parsed: list[tuple[dict[str, Any], T]] = []
        for raw in resources.get(kind, []):
            try:
                parsed.append((raw, model.model_validate(raw)))
            except ValidationError as error:
                refused.append(Refused(f"{kind}/{raw.get('id', '?')}", _reason(error)))
        return parsed

    def taking(kind: str, raw: dict[str, Any], make: Any) -> Any:
        try:
            return make()
        except _UnreadableError as problem:
            refused.append(Refused(f"{kind}/{raw.get('id', '?')}", str(problem)))
            return None

    practitioner_ids = {our_id(str(p.get("id", "")), "S") for p in resources.get("Practitioner", [])}
    roles: dict[str, _PractitionerRole] = {}
    for raw, r in each("PractitionerRole", _PractitionerRole):

        def owner_of(r: _PractitionerRole = r) -> str:
            return _target(r.practitioner, "Practitioner", practitioner_ids, "staff")

        owner = taking("PractitionerRole", raw, owner_of)
        if owner is not None:
            roles[owner] = r
    staff: list[Staff] = []
    for raw, p in each("Practitioner", _Practitioner):
        staff_id = our_id(p.id, "S")

        def make_staff(p: _Practitioner = p, staff_id: str = staff_id) -> Staff:
            role = roles.get(staff_id)
            if role is None:
                raise _UnreadableError("no PractitionerRole")
            return Staff(
                staff_id,
                p.name[0].given[0],
                p.name[0].family,
                _code(role.code, Role),
                _code(role.specialty, Department),
                _address(p.address),
            )

        made = taking("Practitioner", raw, make_staff)
        if made is not None:
            staff.append(made)
    staff_ids = {s.id for s in staff}

    patients = [
        Patient(
            our_id(p.id, "P"),
            p.name[0].given[0],
            p.name[0].family,
            p.birthDate,
            _address(p.address),
            _local(p.deceasedDateTime) if p.deceasedDateTime else None,
        )
        for _, p in each("Patient", _Patient)
    ]
    patient_ids = {p.id for p in patients}

    care_teams: list[CareTeamMember] = []
    for raw, team in each("CareTeam", _CareTeam):

        def make_team(team: _CareTeam = team) -> list[CareTeamMember]:
            patient = _target(team.subject, "Patient", patient_ids, "a patient")
            return [
                CareTeamMember(
                    patient,
                    _target(m.member, "Practitioner", staff_ids, "staff"),
                    _local(m.period.start),
                    _local(m.period.end) if m.period.end else None,
                )
                for m in team.participant
            ]

        care_teams.extend(taking("CareTeam", raw, make_team) or [])

    encounters: list[Encounter] = []
    for raw, e in each("Encounter", _Encounter):

        def make_encounter(e: _Encounter = e) -> Encounter:
            if e.period.end is None:
                raise _UnreadableError("an encounter with no end")
            return Encounter(
                our_id(e.id, "E"),
                _target(e.subject, "Patient", patient_ids, "a patient"),
                tuple(_target(x.individual, "Practitioner", staff_ids, "staff") for x in e.participant),
                _local(e.period.start),
                _local(e.period.end),
            )

        made = taking("Encounter", raw, make_encounter)
        if made is not None:
            encounters.append(made)

    appointments: list[Appointment] = []
    for raw, a in each("Appointment", _Appointment):

        def make_appointment(a: _Appointment = a) -> Appointment:
            actors = [x.actor for x in a.participant]
            patient = next((x for x in actors if x.reference.startswith("Patient/")), None)
            doctor = next((x for x in actors if x.reference.startswith("Practitioner/")), None)
            if patient is None or doctor is None:
                raise _UnreadableError("an appointment without a patient and a staff member")
            return Appointment(
                our_id(a.id, "AP"),
                _target(patient, "Patient", patient_ids, "a patient"),
                _target(doctor, "Practitioner", staff_ids, "staff"),
                _local(a.start),
                _local(a.end),
            )

        made = taking("Appointment", raw, make_appointment)
        if made is not None:
            appointments.append(made)

    accesses: list[Access] = []
    for raw, event in each("AuditEvent", _AuditEvent):

        def make_access(event: _AuditEvent = event) -> Access:
            code = event.subtype[0].code
            if code not in ("read", "search-type"):
                raise _UnreadableError(f"not a chart read or a patient search ({code})")
            agent = event.agent[0]
            who = _target(agent.who, "Practitioner", staff_ids, "staff")
            shown = tuple(_target(x.what, "Patient", patient_ids, "a patient") for x in event.entity)
            if not shown:
                raise _UnreadableError("names no patient")
            chart = code == "read"
            if chart and len(shown) != 1:
                raise _UnreadableError("a chart read naming more than one patient")
            details = {d.type: d.valueString for d in event.entity[0].detail}
            section = None
            seconds = 0
            if chart:
                try:
                    section = Section(details[DETAIL_SECTION])
                    seconds = int(details[DETAIL_SECONDS])
                except (KeyError, ValueError):
                    raise _UnreadableError("a chart read without its section and seconds") from None
            return Access(
                our_id(event.id, "A"),
                who,
                _local(event.recorded),
                AccessKind.CHART if chart else AccessKind.SEARCH,
                shown,
                section,
                seconds,
                agent.network.address,
            )

        made = taking("AuditEvent", raw, make_access)
        if made is not None:
            accesses.append(made)

    clinic = Clinic(
        staff=tuple(sorted(staff, key=lambda s: s.id)),
        patients=tuple(sorted(patients, key=lambda p: p.id)),
        care_teams=tuple(sorted(care_teams, key=lambda m: (m.patient, m.staff, m.start))),
        encounters=tuple(sorted(encounters, key=lambda e: e.id)),
        appointments=tuple(sorted(appointments, key=lambda a: a.id)),
        accesses=tuple(sorted(accesses, key=lambda a: a.id)),
        facts=facts,
    )
    return ReadResult(clinic, refused)


def facts_from_json(saved: dict[str, Any]) -> ClinicFacts:
    """The clinic facts saved in `demo/clinic.json`."""
    return ClinicFacts(
        shifts={
            staff: Shift(time.fromisoformat(shift["start"]), time.fromisoformat(shift["end"]))
            for staff, shift in saved["shifts"].items()
        },
        staff_records=dict(saved["staff_records"]),
        vips=frozenset(saved["vips"]),
    )
