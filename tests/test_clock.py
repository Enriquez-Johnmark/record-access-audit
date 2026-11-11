from datetime import UTC, datetime

from record_access_audit.clock import FixedClock, SystemClock


def test_the_fixed_clock_reads_what_it_was_given() -> None:
    at = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    assert FixedClock(at).now() == at


def test_the_system_clock_is_aware() -> None:
    assert SystemClock().now().tzinfo is not None
