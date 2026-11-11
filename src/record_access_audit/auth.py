"""Logins by emailed link (H1), for the tool's users and, from M5, patients.
A link works once and for 15 minutes; a session lasts 12 hours. Only hashes
of links and session secrets are stored, so the database holds nothing that
logs anyone in."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, cast

from record_access_audit.clock import Clock
from record_access_audit.store.audit import record
from record_access_audit.store.db import Db, transaction

LINK_MINUTES = 15
SESSION_HOURS = 12
CLINIC = "Example Valley Clinic"

Who = Literal["user", "patient"]


@dataclass(frozen=True)
class Session:
    who: Who
    person_id: str
    email: str


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _find(db: Db, email: str) -> tuple[Who, str] | None:
    user = db.execute("select id from users where email = %s", (email,)).fetchone()
    if user is not None:
        return "user", str(user["id"])
    patient = db.execute("select id from patients where lower(email) = %s", (email,)).fetchone()
    if patient is not None:
        return "patient", str(patient["id"])
    return None


def _email(db: Db, who: Who, person_id: str) -> str:
    if who == "user":
        row = db.execute("select email from users where id = %s", (int(person_id),)).fetchone()
    else:
        row = db.execute("select email from patients where id = %s", (person_id,)).fetchone()
    return cast(str, row["email"]) if row else person_id


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


def request_link(db: Db, clock: Clock, email: str, base_url: str) -> Mail | None:
    """Makes a login link if `email` is a user's or a patient's, and returns
    the email to send; the caller sends it after answering, so the answer is
    the same, and as quick, whether or not the address is registered."""
    address = email.strip().lower()
    found = _find(db, address)
    if found is None:
        return None
    who, person_id = found
    token = secrets.token_urlsafe(32)
    now = clock.now()
    db.execute(
        "insert into login_tokens (token_hash, who, person_id, created_at, expires_at)"
        " values (%s, %s, %s, %s, %s)",
        (_hash(token), who, person_id, now, now + timedelta(minutes=LINK_MINUTES)),
    )
    where = f"{CLINIC}'s privacy pages" if who == "user" else f"{CLINIC}'s record access report"
    return Mail(
        address,
        "Your login link",
        f"Open this link to log in to {where} (made up, for a demo):\n\n{base_url}/login/{token}\n\n"
        f"It works once, for {LINK_MINUTES} minutes.",
    )


def use_link(db: Db, clock: Clock, token: str) -> tuple[str, Session] | None:
    """A new session secret if the link is good, else None."""
    now = clock.now()
    with transaction(db):
        row = db.execute(
            "update login_tokens set used_at = %s"
            " where token_hash = %s and used_at is null and expires_at > %s"
            " returning who, person_id",
            (now, _hash(token), now),
        ).fetchone()
        if row is None:
            return None
        who = cast(Who, row["who"])
        person_id = cast(str, row["person_id"])
        email = _email(db, who, person_id)
        secret = secrets.token_urlsafe(32)
        db.execute(
            "insert into sessions (secret_hash, who, person_id, created_at, expires_at)"
            " values (%s, %s, %s, %s, %s)",
            (_hash(secret), who, person_id, now, now + timedelta(hours=SESSION_HOURS)),
        )
        record(db, at=now, actor=email, action="login", subject_type=who, subject_id=person_id)
    return secret, Session(who, person_id, email)


def session_of(db: Db, clock: Clock, secret: str | None) -> Session | None:
    if not secret:
        return None
    row = db.execute(
        "select who, person_id from sessions where secret_hash = %s and expires_at > %s",
        (_hash(secret), clock.now()),
    ).fetchone()
    if row is None:
        return None
    who = cast(Who, row["who"])
    person_id = cast(str, row["person_id"])
    return Session(who, person_id, _email(db, who, person_id))


def end_session(db: Db, secret: str | None) -> None:
    if secret:
        db.execute("delete from sessions where secret_hash = %s", (_hash(secret),))
