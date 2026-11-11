"""Writing to the append-only activity log (G1). Every step calls this in the
same transaction as the change it records."""

from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from record_access_audit.store.db import Db

# The actor for steps the tool takes by itself.
SYSTEM = "system"


def record(
    db: Db,
    *,
    at: datetime,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.execute(
        "insert into audit_events (at, actor, action, subject_type, subject_id, details)"
        " values (%s, %s, %s, %s, %s, %s)",
        (at, actor, action, subject_type, subject_id, Jsonb(details or {})),
    )
