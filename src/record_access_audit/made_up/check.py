"""The repository check behind A3: every FHIR file in the repository is marked
as made-up test data, and nothing outside the research documents
(`docs/research/`, which cite sources) names a real record-system, privacy
monitoring or health-system company."""

import json
import sys
from pathlib import Path
from typing import Any, cast

# Real companies the code, data and docs must not name; matched ignoring case.
REAL_COMPANIES = [
    "Epic Systems",
    "MyChart",
    "Cerner",
    "Oracle Health",
    "Bluesight",
    "PrivacyPro",
    "Protenus",
    "Imprivata",
    "FairWarning",
    "Maize Analytics",
    "iatricSystems",
    "Haystack iS",
    "Veriphyr",
    "Northwestern Memorial",
    "UCLA Health",
    "Montefiore",
    "BayCare",
    "Yakima Valley",
    "Vanderbilt University Medical Center",
    "Penn Medicine",
    "Kaiser Permanente",
    "Mayo Clinic",
    "Cleveland Clinic",
]

# Folders skipped: dependencies, build output, caches and version control.
SKIPPED = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "coverage",
    "test-results",
    "playwright-report",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}

# The research documents, which may name real companies as cited sources.
RESEARCH = "docs/research/"

# This check and its test name what they look for.
SELF = {"src/record_access_audit/made_up/check.py", "tests/test_a3_made_up.py"}

# HL7's "test health data" security label.
TEST_DATA = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST"}


def problems(root: Path) -> list[str]:
    """Every problem found under `root`, one line each, as `path: problem`, sorted."""
    found: list[str] = []
    for path in _files(root):
        shown = path.relative_to(root).as_posix()
        if shown in SELF or shown == ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if shown.endswith((".json", ".ndjson")) and not _marked_as_test_data(
            text, ndjson=shown.endswith(".ndjson")
        ):
            found.append(f"{shown}: a FHIR resource not marked as test data (HTEST)")
        if shown.startswith(RESEARCH):
            continue
        lower = text.lower()
        company = next((c for c in REAL_COMPANIES if c.lower() in lower), None)
        if company:
            found.append(f"{shown}: names a real company ({company})")
    return sorted(found)


def _files(folder: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(folder.iterdir()):
        if path.is_dir():
            if path.name not in SKIPPED:
                files.extend(_files(path))
        elif path.is_file():
            files.append(path)
    return files


def _marked_as_test_data(text: str, *, ndjson: bool) -> bool:
    """Whether a JSON (or NDJSON) file is either not FHIR or FHIR whose every
    resource carries the test-data label."""
    try:
        values = (
            [json.loads(line) for line in text.splitlines() if line.strip()] if ndjson else [json.loads(text)]
        )
    except ValueError:
        return True
    return all(_labelled(resource) for value in values for resource in _resources(value))


def _labelled(resource: dict[str, Any]) -> bool:
    meta = resource.get("meta")
    security = cast(dict[str, Any], meta).get("security") if isinstance(meta, dict) else None
    return isinstance(security, list) and TEST_DATA in cast(list[Any], security)


def _resources(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [r for item in cast(list[Any], value) for r in _resources(item)]
    if not isinstance(value, dict):
        return []
    record = cast(dict[str, Any], value)
    if not isinstance(record.get("resourceType"), str):
        return []
    if record["resourceType"] == "Bundle":
        entries = record.get("entry", [])
        if not isinstance(entries, list):
            return []
        return [
            r
            for entry in cast(list[Any], entries)
            if isinstance(entry, dict)
            for r in _resources(cast(dict[str, Any], entry).get("resource"))
        ]
    return [record]


def main() -> None:
    """`check-made-up`: prints every problem and fails if there is one."""
    found = problems(Path.cwd())
    for line in found:
        print(line)
    sys.exit(1 if found else 0)
