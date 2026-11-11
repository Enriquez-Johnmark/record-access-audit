"""Postgres: connecting and applying the numbered migrations in `migrations/`."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import psycopg
from psycopg.rows import DictRow, dict_row

Db = psycopg.Connection[DictRow]

MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations"
DEFAULT_URL = "postgresql://record_access:record_access@localhost:5432/record_access"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def connect(url: str | None = None) -> Db:
    conn = psycopg.connect(url or database_url(), autocommit=True)
    # Rows as dicts; psycopg's types can't follow the factory set after connecting.
    conn.row_factory = dict_row  # type: ignore[assignment]
    return cast(Db, conn)


@contextmanager
def transaction(db: Db) -> Generator[Db]:
    with db.transaction():
        yield db


def migrate(db: Db) -> list[str]:
    """Applies every migration not yet applied, in order; returns their names."""
    db.execute(
        "create table if not exists schema_migrations"
        " (name text primary key, applied_at timestamptz not null default now())"
    )
    done = {row["name"] for row in db.execute("select name from schema_migrations").fetchall()}
    applied: list[str] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name in done:
            continue
        with transaction(db):
            db.execute(path.read_text())  # type: ignore[arg-type]  # our own migration files
            db.execute("insert into schema_migrations (name) values (%s)", (path.name,))
        applied.append(path.name)
    return applied
