"""The only place that reads the system clock. Everything else takes a Clock."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FixedClock:
    """A clock that reads `at` until moved; for tests and the demo."""

    at: datetime

    def now(self) -> datetime:
        return self.at
