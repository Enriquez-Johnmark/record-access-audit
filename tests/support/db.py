"""A fresh, migrated database for each test that needs one, dropped after."""

import uuid
from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest

from record_access_audit.store.db import Db, connect, database_url, migrate


@pytest.fixture
def db_url() -> Iterator[str]:
    admin_url = database_url()
    name = f"raa_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'create database "{name}"')  # type: ignore[arg-type]
    url = urlunparse(urlparse(admin_url)._replace(path=f"/{name}"))
    with connect(url) as conn:
        migrate(conn)
    try:
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(f'drop database "{name}" with (force)')  # type: ignore[arg-type]


@pytest.fixture
def db(db_url: str) -> Iterator[Db]:
    conn = connect(db_url)
    try:
        yield conn
    finally:
        conn.close()
