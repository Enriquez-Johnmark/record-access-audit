from record_access_audit.core.checks import Check, check
from record_access_audit.core.summary import Sentence, Summary

FACTS = [
    "Staff member S-009 is a nurse in Family Medicine; their shift is 08:00 to 17:00.",
    "At 2026-10-21 11:20, S-009 opened P-286's chart (summary) for 182 seconds.",
    "In all, S-009 opened P-286's chart 2 times, between 2026-10-21 11:20 and 2026-10-21 11:24.",
    "Rule SAME_ADDRESS raised this case: the patient lives at the staff member's home address.",
    "Nothing in the clinic's data accounts for these looks: no care team, visit, appointment or role's work.",
]


def summary(
    *sentences: tuple[str, list[int]], to_check: list[tuple[str, list[int]]] | None = None
) -> Summary:
    return Summary(
        summary=[Sentence(text=t, facts=f) for t, f in sentences],
        to_check=[Sentence(text=t, facts=f) for t, f in (to_check or [])],
    )


GOOD = summary(
    ("S-009, a Family Medicine nurse, opened P-286's chart 2 times on 2026-10-21, from 11:20.", [1, 2, 3]),
    ("The patient lives at the staff member's home address, and no care relationship was found.", [4, 5]),
    to_check=[("Whether S-009 was helping at a visit the record does not show.", [1, 5])],
)


def found(s: Summary) -> list[tuple[Check, str]]:
    return [(p.check, p.found) for p in check(s, FACTS)]


def test_d_a_neutral_summary_citing_its_facts_passes() -> None:
    assert check(GOOD, FACTS) == []


def test_d1_a_sentence_citing_no_fact_or_a_fact_the_case_lacks_is_blocked() -> None:
    assert found(summary(("S-009 opened the chart.", []))) == [
        (Check.CITES_NO_FACT, "S-009 opened the chart.")
    ]
    assert found(summary(("S-009 opened the chart.", [6]))) == [(Check.CITES_NO_FACT, "fact 6")]


def test_d2_a_number_time_or_id_not_in_the_cited_facts_is_blocked() -> None:
    assert found(summary(("S-009 opened P-287's chart.", [2]))) == [(Check.NOT_IN_FACTS, "P-287")]
    assert found(summary(("S-009 opened the chart at 23:40.", [2]))) == [(Check.NOT_IN_FACTS, "23:40")]
    assert found(summary(("S-009 opened the chart three times.", [2]))) == [(Check.NOT_IN_FACTS, "three")]
    assert found(summary(("S-009 opened the chart 2 times.", [2]))) == [(Check.NOT_IN_FACTS, "2")]
    assert found(summary(("S-009 opened the chart 2 times.", [3]))) == []


def test_d3_deciding_or_accusing_words_are_blocked() -> None:
    for text, word in [
        ("S-009 snooped in P-286's chart.", "snooped"),
        ("This was an unauthorized look by S-009.", "unauthorized"),
        ("S-009 violated the policy.", "violated"),
        ("This is a breach.", "breach"),
        ("S-009 should be disciplined.", "disciplined"),
        ("The look by S-009 was inappropriate.", "inappropriate"),
    ]:
        assert found(summary((text, [2]))) == [(Check.ACCUSES, word)]


def test_d4_clinical_words_are_blocked() -> None:
    for text, word in [
        ("P-286 may have diabetes.", "diabetes"),
        ("S-009 looked at P-286's metformin dose.", "metformin"),
        ("P-286's diagnosis was opened.", "diagnosis"),
    ]:
        assert (Check.CLINICAL, word) in found(summary((text, [2])))


def test_d5_a_summary_over_120_words_is_blocked() -> None:
    sentence = " ".join(["S-009 opened P-286's chart."] * 7)
    long = summary(*[(sentence, [2])] * 4, (" ".join(["S-009 opened P-286's chart."] * 6), [2]))
    assert found(long) == [(Check.TOO_LONG, "136 words")]


def test_d6_every_problem_names_its_check_what_it_found_and_where() -> None:
    problems = check(summary(("S-009 snooped at 23:40.", [2]), to_check=[("A breach?", [])]), FACTS)
    assert [(p.check, p.found, p.where) for p in problems] == [
        (Check.NOT_IN_FACTS, "23:40", "summary sentence 1"),
        (Check.ACCUSES, "snooped", "summary sentence 1"),
        (Check.CITES_NO_FACT, "A breach?", "to check 1"),
        (Check.ACCUSES, "breach", "to check 1"),
    ]
    assert all(p.check.description for p in problems)
