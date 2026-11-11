from pathlib import Path

from record_access_audit.evidence import Outcome, build, criteria, gaps, html, outcomes

ROOT = Path(__file__).resolve().parent.parent
SPEC = """### A
- **A1** The data is made up.
- **A2** The model sees no names.
- **B1** Flags come from code.
"""
ARCHITECTURE = """| Milestone | What | Criteria | Status |
|---|---|---|---|
| M1 | Data | A1, A2 | done (2026-11-11) |
| M2 | Flagging | B1 | planned |
"""


def test_j1_links_each_criterion_to_its_passing_tests_by_the_tests_name() -> None:
    evidence = build(
        SPEC,
        ARCHITECTURE,
        [
            Outcome("tests/test_a1.py::test_a1_the_data_is_the_same_every_time", "passed"),
            Outcome("tests/test_a2.py::test_a2_no_name_reaches_the_model", "passed"),
            Outcome("tests/test_a2.py::test_a21_is_not_a2", "failed"),
        ],
    )
    assert [(row.id, row.status) for row in evidence] == [
        ("A1", "proven"),
        ("A2", "proven"),
        ("B1", "not yet due"),
    ]
    assert gaps(evidence) == []
    assert "2 of 3 acceptance criteria proven" in html(evidence, "abc123")


def test_j1_a_finished_milestones_criterion_with_no_passing_test_is_a_gap() -> None:
    evidence = build(SPEC, ARCHITECTURE, [Outcome("t.py::test_a1_the_data", "failed")])
    assert gaps(evidence) == ["A1 (M1): a test failed", "A2 (M1): no test"]


def test_j1_every_criterion_in_the_spec_is_in_a_milestone() -> None:
    spec = (ROOT / "docs" / "product" / "spec.md").read_text()
    architecture = (ROOT / "docs" / "architecture.md").read_text()
    assert len(criteria(spec)) == 34
    assert [row.id for row in build(spec, architecture, []) if row.milestone == ""] == []


def test_j1_reads_pytests_junit_results(tmp_path: Path) -> None:
    xml = tmp_path / "results.xml"
    xml.write_text(
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.test_a1" name="test_a1_ok"/>'
        '<testcase classname="tests.test_a1" name="test_a1_bad"><failure message="x"/></testcase>'
        '<testcase classname="tests.test_a1" name="test_a1_skipped"><skipped/></testcase>'
        "</testsuite></testsuites>"
    )
    assert outcomes(xml) == [
        Outcome("tests.test_a1::test_a1_ok", "passed"),
        Outcome("tests.test_a1::test_a1_bad", "failed"),
        Outcome("tests.test_a1::test_a1_skipped", "skipped"),
    ]


def test_j1_a_skipped_test_neither_proves_nor_fails_a_criterion() -> None:
    evidence = build(
        SPEC,
        ARCHITECTURE,
        [
            Outcome("t.py::test_a1_needs_hapi", "skipped"),
            Outcome("t.py::test_a2_ok", "passed"),
            Outcome("t.py::test_a2_needs_hapi", "skipped"),
            Outcome("t.py::test_b1_needs_hapi", "skipped"),
        ],
    )
    assert [(row.id, row.status) for row in evidence] == [
        ("A1", "missing"),
        ("A2", "proven"),
        ("B1", "not yet due"),
    ]
    assert gaps(evidence) == ["A1 (M1): no test"]
