"""The made-up clinic stored in a test database, and a clock on the demo's last day."""

from datetime import datetime

from record_access_audit.clock import FixedClock
from record_access_audit.made_up.generate import TZ, generate
from record_access_audit.store.clinic import save_clinic
from record_access_audit.store.db import Db

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=TZ)


def stored(db: Db) -> FixedClock:
    save_clinic(db, generate().clinic)
    return FixedClock(NOW)
