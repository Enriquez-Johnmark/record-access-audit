"""Writing and checking each case's summary (C1 to C4, D6). The model gets the
case's numbered facts and nothing else; its answer is parsed strictly and
checked; a summary is shown only if it passes every check. A summary never
touches flags, cases or the queue."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from psycopg.types.json import Jsonb

from record_access_audit.clock import Clock
from record_access_audit.core.cases import CaseKey
from record_access_audit.core.checks import check
from record_access_audit.core.facts import case_facts
from record_access_audit.core.records import Clinic, ClinicFacts
from record_access_audit.core.rules import Flag, RuleCode, RuleSet
from record_access_audit.core.summary import Summary
from record_access_audit.model.client import Summariser, parse_summary, recording_key
from record_access_audit.model.request import SummaryRequest
from record_access_audit.store.audit import SYSTEM, record
from record_access_audit.store.clinic import load_clinic
from record_access_audit.store.db import Db, transaction
from record_access_audit.store.rule_sets import current

Status = Literal["shown", "blocked", "unreadable"]


@dataclass(frozen=True)
class StoredSummary:
    id: int
    model: str
    facts: list[str]
    status: Status
    summary: Summary | None  # set only when shown
    problems: list[dict[str, str]]
    written_at: datetime


def _case(db: Db, case_id: int) -> tuple[CaseKey, list[Flag]]:
    row = db.execute("select staff, patient, day from cases where id = %s", (case_id,)).fetchone()
    if row is None:
        raise KeyError(f"no case {case_id}")
    key = CaseKey(cast(str, row["staff"]), cast("str | None", row["patient"]), row["day"])
    flags = [
        Flag(
            cast(str, r["access"]),
            key.staff,
            key.patient,
            r["day"],
            RuleCode(cast(str, r["code"])),
            int(cast(int, r["version"])),
        )
        for r in db.execute(
            "select f.access, f.code, f.version, (a.at at time zone 'America/Chicago')::date as day"
            " from flags f join accesses a on a.id = f.access where f.case_id = %s order by f.id",
            (case_id,),
        ).fetchall()
    ]
    return key, flags


def _facts(db: Db, clinic: Clinic, rules: RuleSet, case_id: int) -> list[str]:
    key, flags = _case(db, case_id)
    return case_facts(clinic, rules, key, flags)


def facts_for_case(db: Db, clock: Clock, facts: ClinicFacts, case_id: int) -> list[str]:
    """The case's numbered facts, as the privacy officer and the model see them."""
    return _facts(db, load_clinic(db, facts), current(db, clock), case_id)


def summarise(
    db: Db, clock: Clock, model: Summariser, clinic: Clinic, rules: RuleSet, case_id: int, actor: str = SYSTEM
) -> Status:
    facts = _facts(db, clinic, rules, case_id)
    request = SummaryRequest.for_facts(facts, model.model)
    raw = model.answer(request)
    summary = parse_summary(raw)
    problems = check(summary, facts) if summary is not None else []
    status: Status = "unreadable" if summary is None else "blocked" if problems else "shown"
    with transaction(db):
        db.execute(
            "insert into summaries (case_id, model, request_hash, facts, answer, status, problems,"
            " written_at) values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                case_id,
                model.model,
                recording_key(request),
                Jsonb(facts),
                Jsonb(summary.model_dump() if summary is not None else {"raw": raw[:2000]}),
                status,
                Jsonb(
                    [
                        {
                            "check": p.check.value,
                            "found": p.found,
                            "where": p.where,
                            "why": p.check.description,
                        }
                        for p in problems
                    ]
                ),
                clock.now(),
            ),
        )
        record(
            db,
            at=clock.now(),
            actor=actor,
            action=f"summary.{'written' if status == 'shown' else status}",
            subject_type="case",
            subject_id=str(case_id),
            details={"model": model.model, "problems": [f"{p.check.value}: {p.found}" for p in problems]},
        )
    return status


def summarise_open(db: Db, clock: Clock, model: Summariser | None, facts: ClinicFacts) -> dict[str, int]:
    """Summarises every open case that has no summary yet; with no model, nothing (C3)."""
    if model is None:
        return {}
    waiting = [
        int(cast(int, r["id"]))
        for r in db.execute(
            "select id from cases c where not exists (select 1 from decisions d where d.case_id = c.id)"
            " and not exists (select 1 from summaries s where s.case_id = c.id) order by id"
        ).fetchall()
    ]
    if not waiting:
        return {}
    clinic = load_clinic(db, facts)
    rules = current(db, clock)
    return dict(Counter(summarise(db, clock, model, clinic, rules, case_id) for case_id in waiting))


def latest_summary(db: Db, case_id: int) -> StoredSummary | None:
    row = db.execute(
        "select id, model, facts, answer, status, problems, written_at from summaries"
        " where case_id = %s order by id desc limit 1",
        (case_id,),
    ).fetchone()
    if row is None:
        return None
    status = cast(Status, row["status"])
    return StoredSummary(
        id=int(cast(int, row["id"])),
        model=cast(str, row["model"]),
        facts=cast(list[str], row["facts"]),
        status=status,
        summary=Summary.model_validate(row["answer"]) if status == "shown" else None,
        problems=cast(list[dict[str, str]], row["problems"]),
        written_at=cast(datetime, row["written_at"]),
    )
