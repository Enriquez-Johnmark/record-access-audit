"""Reading the append-only activity log (G1 to G3): each case's timeline, and
the whole log filtered by person and step, newest first."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from record_access_audit.store.db import Db


@dataclass(frozen=True)
class Event:
    id: int
    at: datetime
    actor: str
    action: str
    subject_type: str
    subject_id: str
    details: dict[str, Any]


def _events(rows: list[Any]) -> list[Event]:
    return [
        Event(
            int(r["id"]),
            cast(datetime, r["at"]),
            str(r["actor"]),
            str(r["action"]),
            str(r["subject_type"]),
            str(r["subject_id"]),
            cast(dict[str, Any], r["details"]),
        )
        for r in rows
    ]


def timeline(db: Db, case_id: int) -> list[Event]:
    """Every step about one case, oldest first."""
    return _events(
        db.execute(
            "select * from audit_events where subject_type = 'case' and subject_id = %s order by id",
            (str(case_id),),
        ).fetchall()
    )


def activity(db: Db, actor: str | None = None, action: str | None = None, limit: int = 500) -> list[Event]:
    """The whole log, newest first, filtered by person and step when given."""
    return _events(
        db.execute(
            "select * from audit_events where (%s::text is null or actor = %s)"
            " and (%s::text is null or action = %s) order by id desc limit %s",
            (actor, actor, action, action, limit),
        ).fetchall()
    )
