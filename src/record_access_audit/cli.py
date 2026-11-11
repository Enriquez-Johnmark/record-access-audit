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
from record_access_audit.model.client import (
    OWNER_KEY,
    ClaudeSummariser,
    RecordedSummariser,
    RecordingSummariser,
    Summariser,
)
from record_access_audit.model.request import MODEL
from record_access_audit.store.db import connect, migrate
from record_access_audit.summaries import summarise_open

# The clinic facts with no FHIR home, found from the package so any directory works.
FACTS_FILE = Path(__file__).resolve().parents[2] / "demo" / "clinic.json"


def _fhir_url(given: str | None) -> str:
    return given or os.environ.get("FHIR_URL", "http://127.0.0.1:8090/fhir")


def choose_model(recorded: bool, record: bool) -> Summariser | None:
    """Recorded answers, recording, or live Claude with the owner's key; None
    without a key, so cases are shown with their facts alone (C3)."""
    if recorded:
        return RecordedSummariser.from_file(model=MODEL)
    key = os.environ.get(OWNER_KEY)
    if not key:
        if record:
            raise SystemExit(f"recording needs the owner's key in {OWNER_KEY}")
        return None
    live = ClaudeSummariser(key, MODEL)
    return RecordingSummariser(live) if record else live


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="record-access-audit")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="apply the database migrations")
    running = commands.add_parser("run", help="read the access log from the FHIR server and run the rules")
    running.add_argument("--url")

    summarising = commands.add_parser("summarise", help="write a summary for every open case without one")
    how = summarising.add_mutually_exclusive_group()
    how.add_argument("--recorded", action="store_true", help="replay recorded answers: no key, no cost")
    how.add_argument(
        "--record", action="store_true", help="ask Claude for what isn't recorded yet, and save it"
    )

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
    elif args.command == "summarise":
        facts = facts_from_json(json.loads(FACTS_FILE.read_text()))
        with connect() as db:
            counts = summarise_open(db, SystemClock(), choose_model(args.recorded, args.record), facts)
        print(", ".join(f"{n} {status}" for status, n in sorted(counts.items())) or "nothing to summarise")
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
