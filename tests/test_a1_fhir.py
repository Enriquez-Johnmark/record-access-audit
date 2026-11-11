from typing import Any

from record_access_audit.fhir.build import CLINIC_TAG, resources
from record_access_audit.made_up.check import TEST_DATA
from record_access_audit.made_up.generate import generate


def test_a1_every_resource_is_marked_as_test_data_and_tagged_with_the_clinic() -> None:
    built = resources(generate().clinic)
    assert built
    for resource in built:
        assert TEST_DATA in resource["meta"]["security"], resource["id"]
        assert CLINIC_TAG in resource["meta"]["tag"], resource["id"]


def test_a1_the_clinic_is_written_as_the_seven_resource_types() -> None:
    clinic = generate().clinic
    counts: dict[str, int] = {}
    for resource in resources(clinic):
        counts[resource["resourceType"]] = counts.get(resource["resourceType"], 0) + 1
    assert counts == {
        "Practitioner": 30,
        "PractitionerRole": 30,
        "Patient": 300,
        "CareTeam": len({m.patient for m in clinic.care_teams}),
        "Encounter": len(clinic.encounters),
        "Appointment": len(clinic.appointments),
        "AuditEvent": len(clinic.accesses),
    }


def by_type(kind: str) -> list[dict[str, Any]]:
    return [r for r in resources(generate().clinic) if r["resourceType"] == kind]


def test_a1_a_chart_opened_is_a_balp_patient_read_and_a_search_a_patient_query() -> None:
    events = by_type("AuditEvent")
    reads = [e for e in events if e["subtype"][0]["code"] == "read"]
    searches = [e for e in events if e["subtype"][0]["code"] == "search-type"]
    assert reads
    assert searches
    assert len(reads) + len(searches) == len(events)
    read = reads[0]
    assert read["type"]["code"] == "rest"
    assert read["action"] == "R"
    assert read["agent"][0]["who"]["reference"].startswith("Practitioner/")
    assert read["agent"][0]["requestor"] is True
    assert len(read["entity"]) == 1
    assert read["entity"][0]["what"]["reference"].startswith("Patient/")
    assert searches[0]["action"] == "E"
    assert all(e["what"]["reference"].startswith("Patient/") for e in searches[0]["entity"])
