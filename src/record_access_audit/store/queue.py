"""The privacy officer's queue (B5): every open case, ordered by code, by the
sum of its rules' weights, then the oldest first. No model value is read."""

from dataclasses import dataclass
from datetime import date, datetime

from record_access_audit.clock import Clock
from record_access_audit.store.db import Db


@dataclass(frozen=True)
class QueueRow:
    id: int
    staff: str
    patient: str | None
    day: date | None
    codes: list[str]
    score: int
    flagged_at: datetime
    first_access_at: datetime
    age_days: int


QUEUE = """
select c.id, c.staff, c.patient, c.day, c.flagged_at,
       (select sum(w) from (select max(f.weight) as w from flags f where f.case_id = c.id group by f.code) x)
           as score,
       (select array_agg(distinct f.code order by f.code) from flags f where f.case_id = c.id) as codes,
       (select min(a.at) from flags f join accesses a on a.id = f.access where f.case_id = c.id)
           as first_access_at
from cases c
where not exists (select 1 from decisions d where d.case_id = c.id)
order by score desc, c.flagged_at, first_access_at, c.id
"""


def open_cases(db: Db, clock: Clock) -> list[QueueRow]:
    now = clock.now()
    rows = db.execute(QUEUE).fetchall()
    return [
        QueueRow(
            id=r["id"],
            staff=r["staff"],
            patient=r["patient"],
            day=r["day"],
            codes=list(r["codes"]),
            score=int(r["score"]),
            flagged_at=r["flagged_at"],
            first_access_at=r["first_access_at"],
            age_days=(now - r["flagged_at"]).days,
        )
        for r in rows
    ]
