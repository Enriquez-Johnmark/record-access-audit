"""The privacy officer's decisions (E1 to E4): only they decide, each decision
is one of three outcomes with a written reason, and a later decision adds to
the case's history; nothing is replaced. The tool sends no message to anyone."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, cast, get_args

from record_access_audit.clock import Clock
from record_access_audit.people import User
from record_access_audit.store.audit import record
from record_access_audit.store.db import Db, transaction

Outcome = Literal["appropriate", "follow-up", "possible breach"]
OUTCOMES: tuple[str, ...] = get_args(Outcome)
LABELS = {
    "appropriate": "Appropriate",
    "follow-up": "Needs follow-up with the staff member",
    "possible breach": "Possible breach: risk assessment needed",
}
MIN_REASON = 10
REMINDER_DAYS = 60
REMINDER_TEXT = "Reminder only, not legal advice: HIPAA allows at most 60 days from discovery to notify."


class DecisionError(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    id: int
    outcome: Outcome
    reason: str
    decided_by: str
    decided_at: datetime


@dataclass(frozen=True)
class Reminder:
    date: date
    text: str


def decide(db: Db, clock: Clock, user: User, case_id: int, outcome: str, reason: str) -> Decision:
    if user.role != "privacy officer":
        raise DecisionError("only the privacy officer can decide a case")
    if outcome not in OUTCOMES:
        raise DecisionError(f"a decision is one of {', '.join(OUTCOMES)}")
    reason = reason.strip()
    if len(reason) < MIN_REASON:
        raise DecisionError(f"a decision needs a written reason of at least {MIN_REASON} characters")
    now = clock.now()
    with transaction(db):
        if db.execute("select 1 from cases where id = %s", (case_id,)).fetchone() is None:
            raise DecisionError(f"no such case: {case_id}")
        row = db.execute(
            "insert into decisions (case_id, outcome, reason, decided_by, decided_at)"
            " values (%s, %s, %s, %s, %s) returning id",
            (case_id, outcome, reason, user.email, now),
        ).fetchone()
        record(
            db,
            at=now,
            actor=user.email,
            action="decision.recorded",
            subject_type="case",
            subject_id=str(case_id),
            details={"outcome": outcome, "reason": reason},
        )
    assert row is not None
    return Decision(int(cast(int, row["id"])), cast(Outcome, outcome), reason, user.email, now)


def case_decisions(db: Db, case_id: int) -> list[Decision]:
    return [
        Decision(
            int(cast(int, r["id"])),
            cast(Outcome, r["outcome"]),
            cast(str, r["reason"]),
            cast(str, r["decided_by"]),
            cast(datetime, r["decided_at"]),
        )
        for r in db.execute(
            "select id, outcome, reason, decided_by, decided_at from decisions"
            " where case_id = %s order by id",
            (case_id,),
        ).fetchall()
    ]


def reminder_for(decisions: list[Decision]) -> Reminder | None:
    """A 60-day reminder when the latest decision is a possible breach."""
    if not decisions or decisions[-1].outcome != "possible breach":
        return None
    return Reminder((decisions[-1].decided_at + timedelta(days=REMINDER_DAYS)).date(), REMINDER_TEXT)
