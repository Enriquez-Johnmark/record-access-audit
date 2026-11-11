"""Everything the privacy officer sees about one case: who and whose record,
each look (a chart opened shown apart from a search-list hit), the rules, the
facts, the summary if it passed every check, and the decisions. Opening a
case is itself logged (G1)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

from record_access_audit.clock import Clock
from record_access_audit.core.records import ClinicFacts, Department, Role
from record_access_audit.core.rules import DESCRIPTIONS, RuleCode
from record_access_audit.decisions import Decision, Reminder, case_decisions, reminder_for
from record_access_audit.people import User
from record_access_audit.store.audit import record
from record_access_audit.store.db import Db
from record_access_audit.summaries import StoredSummary, facts_for_case, latest_summary


class CaseAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class Look:
    access: str
    at: datetime
    kind: str  # "chart opened" or "search list"
    section: str | None
    seconds: int
    workstation: str


@dataclass(frozen=True)
class CaseView:
    id: int
    status: str  # "open" or the latest decision's outcome
    flagged_at: datetime
    age_days: int
    staff: dict[str, str]
    patient: dict[str, str] | None
    day: date | None
    rules: list[tuple[str, str]]
    looks: list[Look]
    search_hits: list[Look]
    facts: list[str]
    summary: StoredSummary | None
    decisions: list[Decision]
    reminder: Reminder | None


def view_case(db: Db, clock: Clock, user: User, facts: ClinicFacts, case_id: int) -> CaseView:
    if user.role != "privacy officer":
        raise CaseAccessError("only the privacy officer opens a case")
    case = db.execute(
        "select c.id, c.staff, c.patient, c.day, c.flagged_at, s.given, s.family, s.role, s.department"
        " from cases c join staff s on s.id = c.staff where c.id = %s",
        (case_id,),
    ).fetchone()
    if case is None:
        raise KeyError(f"no case {case_id}")
    row = case
    patient = None
    if row["patient"] is not None:
        p = cast(
            dict[str, Any],
            db.execute("select id, given, family from patients where id = %s", (row["patient"],)).fetchone(),
        )
        patient = {"id": p["id"], "name": f"{p['given']} {p['family']}"}
    codes = [
        RuleCode(str(r["code"]))
        for r in db.execute("select distinct code from flags where case_id = %s", (case_id,)).fetchall()
    ]
    codes.sort(key=list(RuleCode).index)
    looks = [
        Look(str(r["id"]), r["at"], str(r["kind"]), r["section"], int(r["seconds"]), str(r["workstation"]))
        for r in db.execute(
            "select distinct a.id, a.at, a.kind, a.section, a.seconds, a.workstation from flags f"
            " join accesses a on a.id = f.access where f.case_id = %s order by a.at, a.id",
            (case_id,),
        ).fetchall()
    ]
    search_hits = []
    if row["patient"] is not None:
        search_hits = [
            Look(str(r["id"]), r["at"], str(r["kind"]), None, 0, str(r["workstation"]))
            for r in db.execute(
                "select id, at, kind, workstation from accesses where staff = %s and kind = 'search list'"
                " and %s = any(patients) order by at, id",
                (row["staff"], row["patient"]),
            ).fetchall()
        ]
    decisions = case_decisions(db, case_id)
    record(
        db,
        at=clock.now(),
        actor=user.email,
        action="case.viewed",
        subject_type="case",
        subject_id=str(case_id),
    )
    return CaseView(
        id=case_id,
        status=decisions[-1].outcome if decisions else "open",
        flagged_at=row["flagged_at"],
        age_days=(clock.now() - row["flagged_at"]).days,
        staff={
            "id": row["staff"],
            "name": f"{row['given']} {row['family']}",
            "role": Role[str(row["role"])].value,
            "department": Department[str(row["department"])].value,
        },
        patient=patient,
        day=row["day"],
        rules=[(code.value, DESCRIPTIONS[code]) for code in codes],
        looks=looks,
        search_hits=search_hits,
        facts=facts_for_case(db, clock, facts, case_id),
        summary=latest_summary(db, case_id),
        decisions=decisions,
        reminder=reminder_for(decisions),
    )
