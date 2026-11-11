"""Running the rules over the stored log (B2, B4): new flags go into the open
case for their staff member and patient (or day), or a new case. An access
and rule already flagged, under any version, is not flagged again, so running
again, or a new version that finds nothing new, adds nothing; no flag is ever
changed."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, cast

from record_access_audit.clock import Clock
from record_access_audit.core.cases import CaseKey, key
from record_access_audit.core.records import ClinicFacts
from record_access_audit.core.rules import Flag, flag
from record_access_audit.fhir.client import FhirServer
from record_access_audit.fhir.reader import Refused, read
from record_access_audit.store.audit import SYSTEM, record
from record_access_audit.store.clinic import load_clinic, save_clinic
from record_access_audit.store.db import Db, transaction
from record_access_audit.store.rule_sets import current

# One run at a time, across every process.
RUN_LOCK = 4_217_101


@dataclass(frozen=True)
class RunResult:
    version: int
    flags: int  # new flags
    cases: int  # new cases


def _open_case(db: Db, case: CaseKey) -> int | None:
    row = db.execute(
        "select id from cases c where staff = %s"
        " and patient is not distinct from %s and day is not distinct from %s"
        " and not exists (select 1 from decisions d where d.case_id = c.id) order by id desc limit 1",
        (case.staff, case.patient, case.day),
    ).fetchone()
    return int(cast(int, row["id"])) if row else None


def run_rules(db: Db, clock: Clock, facts: ClinicFacts, actor: str = SYSTEM) -> RunResult:
    with transaction(db):
        db.execute("select pg_advisory_xact_lock(%s)", (RUN_LOCK,))
        rules = current(db, clock)
        clinic = load_clinic(db, facts)
        existing = {
            (cast(str, r["access"]), cast(str, r["code"]))
            # Evidence already flagged under any version is never flagged again,
            # so a new version adds only what it newly finds.
            for r in db.execute("select distinct access, code from flags").fetchall()
        }
        new: dict[CaseKey, list[Flag]] = defaultdict(list)
        for f in flag(clinic, rules):
            if (f.access, f.code.value) not in existing:
                new[key(f)].append(f)
        now = clock.now()
        opened = 0
        rows: list[tuple[Any, ...]] = []
        for case, flags in sorted(new.items()):
            case_id = _open_case(db, case)
            if case_id is None:
                inserted = db.execute(
                    "insert into cases (staff, patient, day, flagged_at)"
                    " values (%s, %s, %s, %s) returning id",
                    (case.staff, case.patient, case.day, now),
                ).fetchone()
                case_id = int(cast(int, cast(dict[str, Any], inserted)["id"]))
                opened += 1
                record(
                    db,
                    at=now,
                    actor=actor,
                    action="case.flagged",
                    subject_type="case",
                    subject_id=str(case_id),
                    details={"rules": sorted({f.code.value for f in flags}), "version": rules.version},
                )
            rows.extend(
                (f.access, f.code.value, f.version, rules.weights[f.code], case_id, now) for f in flags
            )
        with db.cursor() as cur:
            cur.executemany(
                "insert into flags (access, code, version, weight, case_id, flagged_at)"
                " values (%s, %s, %s, %s, %s, %s)",
                rows,
            )
        record(
            db,
            at=now,
            actor=actor,
            action="rules.run",
            subject_type="rule_set",
            subject_id=str(rules.version),
            details={"flags": len(rows), "cases": opened},
        )
    return RunResult(rules.version, len(rows), opened)


@dataclass(frozen=True)
class FetchResult:
    refused: list[Refused]
    new_accesses: int
    run: RunResult


def fetch_and_run(
    db: Db, clock: Clock, server: FhirServer, facts: ClinicFacts, actor: str = SYSTEM
) -> FetchResult:
    """Reads the clinic from its FHIR server, then stores what is new, records
    it and runs the rules, all in one transaction under the run lock."""
    result = read(server.fetch_clinic(), facts)
    with transaction(db):
        db.execute("select pg_advisory_xact_lock(%s)", (RUN_LOCK,))
        new = save_clinic(db, result.clinic)
        record(
            db,
            at=clock.now(),
            actor=actor,
            action="log.loaded",
            subject_type="fhir",
            subject_id=server.base_url,
            details={"new_accesses": new, "refused": [f"{r.resource}: {r.reason}" for r in result.refused]},
        )
        run = run_rules(db, clock, facts, actor)
    return FetchResult(result.refused, new, run)
