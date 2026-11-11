"""The commands: `record-access-audit <command>`."""

import argparse
import json
import os
import sys
from pathlib import Path

from record_access_audit import evidence
from record_access_audit.audit_run import fetch_and_run
from record_access_audit.clock import SystemClock
from record_access_audit.fhir.client import FhirServer
from record_access_audit.fhir.reader import facts_from_json
from record_access_audit.made_up.generate import generate
from record_access_audit.made_up.load import load
from record_access_audit.store.db import connect, migrate

# The clinic facts with no FHIR home, found from the package so any directory works.
FACTS_FILE = Path(__file__).resolve().parents[2] / "demo" / "clinic.json"


def _fhir_url(given: str | None) -> str:
    return given or os.environ.get("FHIR_URL", "http://127.0.0.1:8090/fhir")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="record-access-audit")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="apply the database migrations")
    running = commands.add_parser("run", help="read the access log from the FHIR server and run the rules")
    running.add_argument("--url")

    loading = commands.add_parser(
        "load-made-up", help="load the made-up clinic into a FHIR server on this computer"
    )
    loading.add_argument("--url")

    pack = commands.add_parser("evidence", help="build the evidence pack from pytest's JUnit results")
    pack.add_argument("--results", required=True, type=Path)
    pack.add_argument("--commit", required=True)
    pack.add_argument("--out", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "migrate":
        with connect() as db:
            applied = migrate(db)
        print(f"applied {len(applied)} migrations")
    elif args.command == "run":
        facts = facts_from_json(json.loads(FACTS_FILE.read_text()))
        with connect() as db:
            result = fetch_and_run(db, SystemClock(), FhirServer(_fhir_url(args.url)), facts)
        for refused in result.refused:
            print(f"refused {refused.resource}: {refused.reason}", file=sys.stderr)
        print(
            f"{result.new_accesses} new accesses; "
            f"{result.run.flags} new flags in {result.run.cases} new cases"
        )
    elif args.command == "load-made-up":
        count = load(_fhir_url(args.url), generate().clinic)
        print(f"loaded {count} made-up resources")
    elif args.command == "evidence":
        root = Path.cwd()
        rows = evidence.build(
            (root / "docs" / "product" / "spec.md").read_text(),
            (root / "docs" / "architecture.md").read_text(),
            evidence.outcomes(args.results),
        )
        args.out.write_text(evidence.html(rows, args.commit))
        missing = evidence.gaps(rows)
        for gap in missing:
            print(gap, file=sys.stderr)
        proven = sum(1 for row in rows if row.status == "proven")
        print(f"{proven} of {len(rows)} acceptance criteria proven")
        if missing:
            sys.exit(1)
