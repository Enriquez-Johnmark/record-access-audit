import copy
import json
from pathlib import Path
from typing import Any

from record_access_audit.fhir.build import resources
from record_access_audit.fhir.client import FhirServer
from record_access_audit.fhir.reader import facts_from_json, read
from record_access_audit.made_up.generate import facts_json, generate

ROOT = Path(__file__).resolve().parent.parent


def grouped(built: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for resource in built:
        by_type.setdefault(resource["resourceType"], []).append(resource)
    return by_type


def test_h2_the_clinic_reads_back_whole_from_its_fhir_resources() -> None:
    clinic = generate().clinic
    result = read(grouped(resources(clinic)), clinic.facts)
    assert result.refused == []
    assert result.clinic == clinic


def test_h2_a_resource_it_cannot_read_is_refused_with_the_reason_and_the_rest_taken_in() -> None:
    clinic = generate().clinic
    by_type = grouped(copy.deepcopy(resources(clinic)))
    events = by_type["AuditEvent"]
    del events[0]["recorded"]
    events[1]["agent"][0]["who"]["reference"] = "Practitioner/evc-s999"
    events[2]["subtype"][0]["code"] = "delete"

    result = read(by_type, clinic.facts)

    assert [(r.resource, r.reason) for r in result.refused] == [
        (f"AuditEvent/{events[0]['id']}", "recorded: Field required"),
        (f"AuditEvent/{events[1]['id']}", "names staff not in the clinic (Practitioner/evc-s999)"),
        (f"AuditEvent/{events[2]['id']}", "not a chart read or a patient search (delete)"),
    ]
    assert len(result.clinic.accesses) == len(clinic.accesses) - 3
    assert len(result.clinic.patients) == 300


def test_h2_the_saved_clinic_facts_are_the_generated_ones() -> None:
    saved = json.loads((ROOT / "demo" / "clinic.json").read_text())
    assert saved == facts_json(generate().clinic.facts)
    assert facts_from_json(saved) == generate().clinic.facts


def test_h2_the_clinic_loaded_into_hapi_is_read_back_whole(loaded_fhir: FhirServer) -> None:
    clinic = generate().clinic
    result = read(loaded_fhir.fetch_clinic(), clinic.facts)
    assert result.refused == []
    assert result.clinic == clinic


def test_h2_wrong_ids_types_and_empty_lists_are_refused_one_resource_at_a_time() -> None:
    clinic = generate().clinic
    by_type = grouped(copy.deepcopy(resources(clinic)))
    events = by_type["AuditEvent"]
    events[0]["agent"][0]["who"]["reference"] = "Practitioner/evc-p002"
    events[1]["recorded"] = 1730000000
    events[2]["agent"][0]["requestor"] = 1
    events[3]["subtype"] = []
    patients = by_type["Patient"]
    patients[0]["name"] = []
    patients[1]["deceasedDateTime"] = "2026-01-01T00:00:00"
    by_type["PractitionerRole"].append({**by_type["PractitionerRole"][0], "id": "evc-r999"})

    result = read(by_type, clinic.facts)

    reasons = {r.resource: r.reason for r in result.refused}
    assert (
        reasons[f"AuditEvent/{events[0]['id']}"]
        == "not one of the clinic's staff IDs (Practitioner/evc-p002)"
    )
    assert reasons[f"AuditEvent/{events[1]['id']}"].startswith("recorded:")
    assert reasons[f"AuditEvent/{events[2]['id']}"].startswith("agent.0.requestor:")
    assert reasons[f"AuditEvent/{events[3]['id']}"].startswith("subtype:")
    assert reasons[f"Patient/{patients[0]['id']}"].startswith("name:")
    assert reasons[f"Patient/{patients[1]['id']}"] == "a time without a time zone"
    assert reasons["PractitionerRole/evc-r999"] == "a second PractitionerRole for Practitioner/evc-s001"
    assert next(s for s in result.clinic.staff if s.id == "S-001").role == clinic.staff[0].role
    assert len(result.clinic.patients) == 298


def test_h2_the_run_command_finds_the_clinic_facts_from_any_directory() -> None:
    from record_access_audit.cli import FACTS_FILE

    assert FACTS_FILE.is_absolute()
    assert FACTS_FILE == ROOT / "demo" / "clinic.json"
