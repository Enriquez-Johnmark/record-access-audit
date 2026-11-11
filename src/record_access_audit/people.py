"""The tool's users: the privacy officer, who decides cases and edits the
rules, and the administrator, who loads the log and reads the activity log."""

from dataclasses import dataclass
from typing import Literal, cast

from record_access_audit.store.db import Db

UserRole = Literal["privacy officer", "administrator"]


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: str
    role: UserRole


def add_user(db: Db, email: str, name: str, role: UserRole) -> User:
    row = db.execute(
        "insert into users (email, name, role) values (lower(%s), %s, %s)"
        " on conflict (email) do update set name = excluded.name, role = excluded.role"
        " returning id, email, name, role",
        (email.strip(), name, role),
    ).fetchone()
    assert row is not None
    return User(
        int(cast(int, row["id"])),
        cast(str, row["email"]),
        cast(str, row["name"]),
        cast(UserRole, row["role"]),
    )


def user_by_id(db: Db, user_id: int) -> User | None:
    row = db.execute("select id, email, name, role from users where id = %s", (user_id,)).fetchone()
    if row is None:
        return None
    return User(
        int(cast(int, row["id"])),
        cast(str, row["email"]),
        cast(str, row["name"]),
        cast(UserRole, row["role"]),
    )
