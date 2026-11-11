from pathlib import Path

from record_access_audit.core.rules import DEFAULT_RULES
from record_access_audit.made_up.generate import generate
from record_access_audit.measure import measure_summaries, report_markdown
from record_access_audit.model.client import RecordedSummariser

ROOT = Path(__file__).resolve().parent.parent


def test_i3_at_least_90_percent_of_claudes_recorded_summaries_pass_and_every_failure_is_listed() -> None:
    results = measure_summaries(generate(), DEFAULT_RULES, RecordedSummariser.from_file())
    assert len(results) == 34
    assert all(r.status != "not recorded" for r in results)
    passed = [r for r in results if r.status == "shown"]
    assert len(passed) / len(results) >= 0.9
    report = report_markdown(generate(), DEFAULT_RULES, RecordedSummariser.from_file())
    for failed in (r for r in results if r.status != "shown"):
        assert failed.case in report


def test_i3_the_committed_report_is_the_one_the_recordings_give() -> None:
    report = report_markdown(generate(), DEFAULT_RULES, RecordedSummariser.from_file())
    assert (ROOT / "evalset" / "report.md").read_text() == report
