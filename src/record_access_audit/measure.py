"""Measurement (I1 to I3). Flagging on the labelled made-up log: whether every
planted case is flagged, each rule's recall and precision, and how much of the
log the clinic's own data accounts for. It never claims to catch real snooping."""

from dataclasses import dataclass

from record_access_audit.core.accounting import Index, reasons
from record_access_audit.core.cases import CaseKey, group
from record_access_audit.core.records import AccessKind
from record_access_audit.core.rules import RuleCode, RuleSet, flag
from record_access_audit.made_up.generate import Label, MadeUp


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
