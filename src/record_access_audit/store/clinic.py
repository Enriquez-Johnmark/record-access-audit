"""Storing the clinic read from its FHIR server, so the rules, the facts and
the patient report never call the server mid-request. Saving again adds only
what is new; nothing already stored is changed."""

from typing import Any, cast
from zoneinfo import ZoneInfo

from record_access_audit.core.records import (
    CLINIC_TIME_ZONE,
    Access,
    AccessKind,
    Address,
    Appointment,
    CareTeamMember,
    Clinic,
    ClinicFacts,
    Department,
    Encounter,
    Patient,
    Role,
    Section,
    Staff,
)
from record_access_audit.store.db import Db, transaction

TZ = ZoneInfo(CLINIC_TIME_ZONE)


def save_clinic(db: Db, clinic: Clinic) -> int:
    """Stores everything not yet stored; returns how many new accesses."""
    with transaction(db), db.cursor() as cur:
        cur.executemany(
            "insert into staff values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
            [
                (
                    s.id,
                    s.given,
                    s.family,
                    s.role.name,
                    s.department.name,
                    s.address.line,
                    s.address.city,
                    s.address.postal_code,
                )
                for s in clinic.staff
            ],
        )
        cur.executemany(
            "insert into patients values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
            [
                (
                    p.id,
                    p.given,
                    p.family,
                    p.birth_date,
                    p.address.line,
                    p.address.city,
                    p.address.postal_code,
                    p.deceased_at,
                )
                for p in clinic.patients
            ],
        )
        cur.executemany(
            "insert into care_team_members values (%s, %s, %s, %s) on conflict do nothing",
            [(m.patient, m.staff, m.start, m.end) for m in clinic.care_teams],
        )
        cur.executemany(
            "insert into encounters values (%s, %s, %s, %s, %s) on conflict do nothing",
            [(e.id, e.patient, list(e.staff), e.start, e.end) for e in clinic.encounters],
        )
        cur.executemany(
            "insert into appointments values (%s, %s, %s, %s, %s) on conflict do nothing",
            [(a.id, a.patient, a.staff, a.start, a.end) for a in clinic.appointments],
        )
        before = _count(db, "accesses")
        cur.executemany(
            "insert into accesses values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
            [
                (
                    a.id,
                    a.staff,
                    a.at,
                    a.kind.value,
                    list(a.patients),
                    a.section.value if a.section else None,
                    a.seconds,
                    a.workstation,
                )
                for a in clinic.accesses
            ],
        )
        return _count(db, "accesses") - before


def _count(db: Db, table: str) -> int:
    row = db.execute(f"select count(*) as n from {table}").fetchone()  # type: ignore[arg-type]  # noqa: S608
    return int(cast(dict[str, Any], row)["n"])


def _local(value: Any) -> Any:
    return value.astimezone(TZ) if value is not None else None


def _address(row: dict[str, Any]) -> Address:
    return Address(row["address_line"], row["city"], row["postal_code"])


def load_clinic(db: Db, facts: ClinicFacts) -> Clinic:
    def rows(sql: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], db.execute(sql).fetchall())  # type: ignore[arg-type]

    return Clinic(
        staff=tuple(
            Staff(r["id"], r["given"], r["family"], Role[r["role"]], Department[r["department"]], _address(r))
            for r in rows("select * from staff order by id")
        ),
        patients=tuple(
            Patient(r["id"], r["given"], r["family"], r["birth_date"], _address(r), _local(r["deceased_at"]))
            for r in rows("select * from patients order by id")
        ),
        care_teams=tuple(
            CareTeamMember(r["patient"], r["staff"], _local(r["start_at"]), _local(r["end_at"]))
            for r in rows("select * from care_team_members order by patient, staff, start_at")
        ),
        encounters=tuple(
            Encounter(r["id"], r["patient"], tuple(r["staff"]), _local(r["start_at"]), _local(r["end_at"]))
            for r in rows("select * from encounters order by id")
        ),
        appointments=tuple(
            Appointment(r["id"], r["patient"], r["staff"], _local(r["start_at"]), _local(r["end_at"]))
            for r in rows("select * from appointments order by id")
        ),
        accesses=tuple(
            Access(
                r["id"],
                r["staff"],
                _local(r["at"]),
                AccessKind(r["kind"]),
                tuple(r["patients"]),
                Section(r["section"]) if r["section"] else None,
                r["seconds"],
                r["workstation"],
            )
            for r in rows("select * from accesses order by id")
        ),
        facts=facts,
    )
