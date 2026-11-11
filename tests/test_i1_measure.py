from record_access_audit.core.rules import DEFAULT_RULES, RuleCode
from record_access_audit.made_up.generate import generate
from record_access_audit.measure import measure_flagging


def test_i1_every_planted_case_is_flagged_and_each_rules_precision_is_reported() -> None:
    report = measure_flagging(generate(), DEFAULT_RULES)

    assert report.planted == 31
    assert report.planted_flagged == 31
    assert report.look_alikes == 21
    assert report.false_alarms == 3
    by_rule = {m.code: m for m in report.rules}
    assert set(by_rule) == set(RuleCode)
    assert all(m.recall == 1.0 for m in report.rules)
    assert by_rule[RuleCode.NO_RELATIONSHIP].cases == 29
    assert by_rule[RuleCode.NO_RELATIONSHIP].precision == 26 / 29
    assert all(m.precision == 1.0 for m in report.rules if m.code is not RuleCode.NO_RELATIONSHIP)


def test_i1_the_share_of_charts_opened_that_the_clinics_data_accounts_for_is_reported() -> None:
    report = measure_flagging(generate(), DEFAULT_RULES)
    assert report.charts_opened > 2000
    assert 0 < report.charts_accounted < report.charts_opened
    assert 0.9 < report.share_accounted < 1.0
