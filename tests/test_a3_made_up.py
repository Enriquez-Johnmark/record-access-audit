import json
from pathlib import Path

from record_access_audit.made_up.check import TEST_DATA, problems

ROOT = Path(__file__).resolve().parent.parent


def folder(tmp_path: Path, files: dict[str, str]) -> Path:
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    return tmp_path


def test_a3_the_repository_itself_passes() -> None:
    assert problems(ROOT) == []


def test_a3_a_real_company_outside_the_research_is_found_inside_it_is_allowed(tmp_path: Path) -> None:
    root = folder(
        tmp_path,
        {
            "README.md": "Works like Imprivata's privacy monitoring.",
            "docs/research/README.md": "Imprivata sells monitoring (vendor claim).",
        },
    )
    assert problems(root) == ["README.md: names a real company (Imprivata)"]


def test_a3_a_fhir_resource_not_marked_as_test_data_is_found(tmp_path: Path) -> None:
    marked = {"resourceType": "Patient", "id": "y", "meta": {"security": [TEST_DATA]}}
    bundle = {
        "resourceType": "Bundle",
        "entry": [{"resource": marked}, {"resource": {"resourceType": "AuditEvent"}}],
    }
    root = folder(
        tmp_path,
        {
            "demo/patient.json": json.dumps({"resourceType": "Patient", "id": "x"}),
            "demo/marked.json": json.dumps(marked),
            "demo/bundle.json": json.dumps(bundle),
            "demo/not-fhir.json": json.dumps({"rules": []}),
        },
    )
    assert problems(root) == [
        "demo/bundle.json: a FHIR resource not marked as test data (HTEST)",
        "demo/patient.json: a FHIR resource not marked as test data (HTEST)",
    ]
