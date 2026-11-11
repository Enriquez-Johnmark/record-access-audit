"""The clinic's records written as FHIR R4 resources: staff as `Practitioner`
and `PractitionerRole`, patients, their `CareTeam`s, `Encounter`s and
`Appointment`s, and each access as an `AuditEvent` shaped like IHE BALP
`PatientRead` (a chart opened) or `PatientQuery` (a search list). Every
resource is marked as test data and tagged with the clinic."""

import re
from datetime import date, datetime
from typing import Any

from record_access_audit.core.records import (
    Access,
    AccessKind,
    Address,
    Appointment,
    Clinic,
    Encounter,
    Patient,
    Staff,
)
from record_access_audit.made_up.check import TEST_DATA

Resource = dict[str, Any]

BASE = "urn:example:record-access-audit"
CLINIC_TAG = {"system": f"{BASE}:clinic", "code": "example-valley-clinic"}
STAFF_ID = f"{BASE}:staff"
PATIENT_ID = f"{BASE}:patient"
ROLE_CODES = f"{BASE}:role"
DEPARTMENT_CODES = f"{BASE}:department"
DETAIL_SECTION = "section"
DETAIL_SECONDS = "seconds"
CLINIC_NAME = "Example Valley Clinic"

AUDIT_TYPE = {
    "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
    "code": "rest",
    "display": "RESTful Operation",
}
INTERACTION = "http://hl7.org/fhir/restful-interaction"
ENTITY_TYPE = {"system": "http://terminology.hl7.org/CodeSystem/audit-entity-type", "code": "1"}
PATIENT_ROLE = {"system": "http://terminology.hl7.org/CodeSystem/object-role", "code": "1"}


def fhir_id(our_id: str) -> str:
    """`S-001` -> `evc-s001`: our IDs as FHIR resource IDs."""
    return "evc-" + our_id.lower().replace("-", "")


def our_id(resource_id: str, prefix: str) -> str:
    """`evc-s001` -> `S-001`, given the ID's letters (`S`, `P`, `A`, `E`, `AP`).
    Anything not shaped exactly like one of our IDs is a ValueError."""
    match = re.fullmatch(rf"evc-{prefix.lower()}(\d+)", resource_id)
    if match is None:
        raise ValueError(f"not one of our {prefix} IDs: {resource_id}")
    return f"{prefix}-{match[1]}"


def _meta() -> dict[str, Any]:
    return {"security": [dict(TEST_DATA)], "tag": [dict(CLINIC_TAG)]}


def _when(at: datetime) -> str:
    return at.isoformat()


def _address(address: Address, use: str) -> dict[str, Any]:
    return {"use": use, "line": [address.line], "city": address.city, "postalCode": address.postal_code}


def _ref(kind: str, our: str) -> dict[str, str]:
    return {"reference": f"{kind}/{fhir_id(our)}"}


def _staff(staff: Staff) -> list[Resource]:
    practitioner: Resource = {
        "resourceType": "Practitioner",
        "id": fhir_id(staff.id),
        "meta": _meta(),
        "identifier": [{"system": STAFF_ID, "value": staff.id}],
        "name": [{"family": staff.family, "given": [staff.given]}],
        "address": [_address(staff.address, "home")],
    }
    role: Resource = {
        "resourceType": "PractitionerRole",
        "id": fhir_id(staff.id.replace("S-", "R-")),
        "meta": _meta(),
        "practitioner": _ref("Practitioner", staff.id),
        "code": [{"coding": [{"system": ROLE_CODES, "code": staff.role.name, "display": staff.role.value}]}],
        "specialty": [
            {
                "coding": [
                    {
                        "system": DEPARTMENT_CODES,
                        "code": staff.department.name,
                        "display": staff.department.value,
                    }
                ]
            }
        ],
    }
    return [practitioner, role]


def _patient(patient: Patient) -> Resource:
    resource: Resource = {
        "resourceType": "Patient",
        "id": fhir_id(patient.id),
        "meta": _meta(),
        "identifier": [{"system": PATIENT_ID, "value": patient.id}],
        "name": [{"family": patient.family, "given": [patient.given]}],
        "birthDate": patient.birth_date.isoformat(),
        "address": [_address(patient.address, "home")],
    }
    if patient.deceased_at is not None:
        resource["deceasedDateTime"] = _when(patient.deceased_at)
    if patient.email is not None:
        resource["telecom"] = [{"system": "email", "value": patient.email}]
    return resource


def _care_team(patient: str, clinic: Clinic) -> Resource:
    participants: list[dict[str, Any]] = []
    for member in clinic.care_teams:
        if member.patient != patient:
            continue
        period = {"start": _when(member.start)}
        if member.end is not None:
            period["end"] = _when(member.end)
        participants.append({"member": _ref("Practitioner", member.staff), "period": period})
    return {
        "resourceType": "CareTeam",
        "id": fhir_id(patient.replace("P-", "CT-")),
        "meta": _meta(),
        "status": "active",
        "subject": _ref("Patient", patient),
        "participant": participants,
    }


def _encounter(encounter: Encounter) -> Resource:
    return {
        "resourceType": "Encounter",
        "id": fhir_id(encounter.id),
        "meta": _meta(),
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "subject": _ref("Patient", encounter.patient),
        "participant": [{"individual": _ref("Practitioner", s)} for s in encounter.staff],
        "period": {"start": _when(encounter.start), "end": _when(encounter.end)},
    }


def _appointment(appointment: Appointment, today: date) -> Resource:
    return {
        "resourceType": "Appointment",
        "id": fhir_id(appointment.id),
        "meta": _meta(),
        "status": "fulfilled" if appointment.start.date() < today else "booked",
        "start": _when(appointment.start),
        "end": _when(appointment.end),
        "participant": [
            {"actor": _ref("Patient", appointment.patient), "status": "accepted"},
            {"actor": _ref("Practitioner", appointment.staff), "status": "accepted"},
        ],
    }


def _audit_event(access: Access) -> Resource:
    chart = access.kind is AccessKind.CHART
    entities: list[dict[str, Any]] = []
    for patient in access.patients:
        entity: dict[str, Any] = {"what": _ref("Patient", patient), "type": ENTITY_TYPE, "role": PATIENT_ROLE}
        if chart:
            entity["detail"] = [
                {
                    "type": DETAIL_SECTION,
                    "valueString": access.section.value if access.section else "summary",
                },
                {"type": DETAIL_SECONDS, "valueString": str(access.seconds)},
            ]
        entities.append(entity)
    return {
        "resourceType": "AuditEvent",
        "id": fhir_id(access.id),
        "meta": _meta(),
        "type": AUDIT_TYPE,
        "subtype": [{"system": INTERACTION, "code": "read" if chart else "search-type"}],
        "action": "R" if chart else "E",
        "recorded": _when(access.at),
        "outcome": "0",
        "agent": [
            {
                "who": _ref("Practitioner", access.staff),
                "requestor": True,
                "network": {"address": access.workstation, "type": "1"},
            }
        ],
        "source": {"site": CLINIC_NAME, "observer": {"display": f"{CLINIC_NAME} record system (made up)"}},
        "entity": entities,
    }


def resources(clinic: Clinic) -> list[Resource]:
    """Every resource for `clinic`, in a fixed order."""
    today = max(a.at for a in clinic.accesses).date()
    built: list[Resource] = []
    for staff in clinic.staff:
        built.extend(_staff(staff))
    built.extend(_patient(p) for p in clinic.patients)
    built.extend(_care_team(p, clinic) for p in sorted({m.patient for m in clinic.care_teams}))
    built.extend(_encounter(e) for e in clinic.encounters)
    built.extend(_appointment(a, today) for a in clinic.appointments)
    built.extend(_audit_event(a) for a in clinic.accesses)
    return built
