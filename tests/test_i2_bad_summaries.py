import json
from pathlib import Path

from record_access_audit.core.checks import Check, check
from record_access_audit.core.summary import Summary

ROOT = Path(__file__).resolve().parent.parent


def test_i2_all_30_bad_summaries_are_blocked_each_by_the_check_it_was_written_to_trip() -> None:
    items = json.loads((ROOT / "evalset" / "bad-summaries.json").read_text())["summaries"]
    assert len(items) == 30
    for check_name in Check:
        assert sum(1 for item in items if item["trips"] == check_name.value) == 6, check_name
    for item in items:
        summary = Summary.model_validate(item["summary"])
        assert {p.check.value for p in check(summary, item["facts"])} == {item["trips"]}, item["id"]
