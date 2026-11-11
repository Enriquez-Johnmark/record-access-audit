"""Measurement (I1 to I3). Flagging on the labelled made-up log: whether every
planted case is flagged, each rule's recall and precision, and how much of the
log the clinic's own data accounts for. It never claims to catch real snooping."""

import json
from dataclasses import dataclass
from pathlib import Path

from record_access_audit.core.accounting import Index, reasons
from record_access_audit.core.cases import CaseKey, group
from record_access_audit.core.cases import key as case_key
from record_access_audit.core.checks import check
from record_access_audit.core.facts import case_facts
from record_access_audit.core.records import AccessKind
from record_access_audit.core.rules import RuleCode, RuleSet, flag
from record_access_audit.core.summary import Summary
from record_access_audit.made_up.generate import Label, MadeUp
from record_access_audit.model.client import NotRecordedError, Summariser, parse_summary
from record_access_audit.model.request import SummaryRequest

EVALSET = Path(__file__).resolve().parents[2] / "evalset"


@dataclass(frozen=True)
class RuleMeasure:
    code: RuleCode
    cases: int  # cases this rule raised
    true_cases: int  # of them, planted cases
    expected: int  # planted cases labelled with this rule
    found: int  # of them, raised with this rule

    @property
    def precision(self) -> float:
        return self.true_cases / self.cases if self.cases else 1.0

    @property
    def recall(self) -> float:
        return self.found / self.expected if self.expected else 1.0


@dataclass(frozen=True)
class FlagReport:
    planted: int
    planted_flagged: int
    look_alikes: int
    false_alarms: int
    rules: list[RuleMeasure]
    charts_opened: int
    charts_accounted: int

    @property
    def share_accounted(self) -> float:
        return self.charts_accounted / self.charts_opened


def _case(label: Label) -> CaseKey:
    return CaseKey(label.staff, label.patient, None if label.patient else label.day)


def measure_flagging(made: MadeUp, rules: RuleSet) -> FlagReport:
    found = group(flag(made.clinic, rules))
    planted = {_case(label): label for label in made.labels if label.planted}
    look_alikes = [label for label in made.labels if not label.planted]
    measures: list[RuleMeasure] = []
    for code in RuleCode:
        raised = [case for case, codes in found.items() if code in codes]
        expected = [label for label in planted.values() if code in label.rules]
        measures.append(
            RuleMeasure(
                code,
                cases=len(raised),
                true_cases=sum(1 for case in raised if case in planted),
                expected=len(expected),
                found=sum(1 for label in expected if code in found.get(_case(label), set())),
            )
        )
    index = Index(made.clinic, rules)
    charts = [a for a in made.clinic.accesses if a.kind is AccessKind.CHART]
    accounted = sum(1 for a in charts if reasons(index, a.staff, a.patients[0], a.at))
    return FlagReport(
        planted=len(planted),
        planted_flagged=sum(
            1 for case, label in planted.items() if set(label.rules) <= found.get(case, set())
        ),
        look_alikes=len(look_alikes),
        false_alarms=sum(1 for label in look_alikes if _case(label) in found),
        rules=measures,
        charts_opened=len(charts),
        charts_accounted=accounted,
    )


@dataclass(frozen=True)
class SummaryResult:
    case: str  # "S-008/P-181", or "S-023/2026-10-29" for a day
    status: str  # shown, blocked, unreadable or not recorded
    problems: list[str]


def measure_summaries(made: MadeUp, rules: RuleSet, model: Summariser) -> list[SummaryResult]:
    """I3: each case's recorded summary, put through the same checks as live ones."""
    flags = flag(made.clinic, rules)
    results: list[SummaryResult] = []
    for key in sorted(group(flags)):
        own = [f for f in flags if case_key(f) == key]
        facts = case_facts(made.clinic, rules, key, own)
        name = f"{key.staff}/{key.patient or key.day}"
        try:
            raw = model.answer(SummaryRequest.for_facts(facts, model.model))
        except NotRecordedError:
            results.append(SummaryResult(name, "not recorded", []))
            continue
        summary = parse_summary(raw)
        if summary is None:
            results.append(SummaryResult(name, "unreadable", []))
            continue
        ids = frozenset(i for i in (key.staff, key.patient) if i)
        problems = [f"{p.check.value}: {p.found} ({p.where})" for p in check(summary, facts, ids)]
        results.append(SummaryResult(name, "blocked" if problems else "shown", problems))
    return results


def _bad_summaries() -> list[tuple[str, set[str]]]:
    items = json.loads((EVALSET / "bad-summaries.json").read_text())["summaries"]
    return [
        (
            item["trips"],
            {p.check.value for p in check(Summary.model_validate(item["summary"]), item["facts"])},
        )
        for item in items
    ]


def _percent(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "n/a"


def report_markdown(made: MadeUp, rules: RuleSet, model: Summariser) -> str:
    """The measurement report, `evalset/report.md`; the same every time for the same recordings."""
    flagging = measure_flagging(made, rules)
    bad = _bad_summaries()
    summaries = measure_summaries(made, rules, model)
    shown = sum(1 for r in summaries if r.status == "shown")
    lines = [
        "# Measurement",
        "",
        "Made by `record-access-audit measure` from the made-up log (`evalset/labels.json`), the hand-written"
        " bad summaries (`evalset/bad-summaries.json`) and Claude's recorded summaries"
        " (`evalset/recorded/summaries.json`). Everyone in it is made up. It measures the tool on a log built"
        " to test it; it says nothing about catching real snooping.",
        "",
        "## Flagging (I1)",
        "",
        f"- Planted cases flagged with every rule they were planted for: **{flagging.planted_flagged} of"
        f" {flagging.planted}**.",
        f"- Innocent look-alikes flagged anyway (false alarms): **{flagging.false_alarms} of {flagging.look_alikes}**,"
        " all of them a nurse covering a visit the record doesn't show.",
        f"- Charts opened that the clinic's own data accounts for: **{flagging.charts_accounted} of"
        f" {flagging.charts_opened} ({_percent(flagging.charts_accounted, flagging.charts_opened)})**.",
        "",
        "| Rule | Cases raised | Of them planted | Precision | Planted cases expected | Found | Recall |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in flagging.rules:
        lines.append(
            f"| `{m.code.value}` | {m.cases} | {m.true_cases} | {_percent(m.true_cases, m.cases)} | {m.expected}"
            f" | {m.found} | {_percent(m.found, m.expected)} |"
        )
    blocked_as_meant = sum(1 for trips, found in bad if found == {trips})
    lines += [
        "",
        "## Bad summaries (I2)",
        "",
        f"**{blocked_as_meant} of {len(bad)}** hand-written bad summaries are blocked, each by exactly the check it"
        " was written to trip.",
        "",
        "| Check | Bad summaries | Blocked by it |",
        "|---|---|---|",
    ]
    for name in sorted({trips for trips, _ in bad}):
        mine = [found for trips, found in bad if trips == name]
        lines.append(f"| `{name}` | {len(mine)} | {sum(1 for found in mine if name in found)} |")
    lines += [
        "",
        "## Claude's summaries (I3)",
        "",
        f"Claude ({model.model}) wrote a summary of every case from its numbered facts; recorded once with the"
        f" owner's key and replayed here. **{shown} of {len(summaries)} ({_percent(shown, len(summaries))}) pass"
        " every check.**",
        "",
        "On the first recorded run, 29 of 34 passed. Three of the five blocked named the case's own patient in a"
        " sentence citing a fact without that ID; the check now lets a summary name its own case's staff member"
        " and patient, with a test.",
        "",
    ]
    failures = [r for r in summaries if r.status != "shown"]
    if failures:
        lines += [
            'Each summary still blocked, with what the checks found. A number word such as "two" must match a'
            " number in the cited facts, whether it counts something or not: the check can't tell the uses apart.",
            "",
            "| Case | Status | Problems |",
            "|---|---|---|",
        ]
        lines += [f"| {r.case} | {r.status} | {'; '.join(r.problems)} |" for r in failures]
    else:
        lines.append("Every summary passed.")
    return "\n".join(lines) + "\n"
