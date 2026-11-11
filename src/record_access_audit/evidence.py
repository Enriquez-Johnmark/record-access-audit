"""The evidence pack (J1): each acceptance criterion in the spec, the tests
that prove it (found by the test's name, `test_<id>_...`), and whether they
passed. A criterion of a milestone marked done needs at least one passing test."""

import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

Status = Literal["proven", "failing", "missing", "not yet due"]
Result = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class Outcome:
    name: str
    result: Result

    @property
    def passed(self) -> bool:
        return self.result == "passed"


@dataclass(frozen=True)
class Row:
    id: str
    text: str
    milestone: str
    tests: list[Outcome]
    status: Status


@dataclass(frozen=True)
class Milestone:
    name: str
    ids: list[str]
    done: bool


def criteria(spec: str) -> list[tuple[str, str]]:
    """The criteria in the spec, from lines like `- **A1** The text.`"""
    return [(m[1], m[2].strip()) for m in re.finditer(r"^- \*\*([A-Z]\d+)\*\* (.+)$", spec, re.MULTILINE)]


def milestones(architecture: str) -> list[Milestone]:
    """The build order, from rows like `| M1 | What | A1, B1–B3 | done |`."""
    rows = re.finditer(r"^\| (M\d+) \| [^|]+ \| ([^|]+) \| ([^|]+) \|$", architecture, re.MULTILINE)
    return [Milestone(m[1], _expand(m[2]), m[3].strip().startswith("done")) for m in rows]


def _expand(listed: str) -> list[str]:
    """`A1, B1–B3` -> A1, B1, B2, B3."""
    ids: list[str] = []
    for part in (p.strip() for p in listed.split(",")):
        span = re.fullmatch(r"([A-Z])(\d+)[–-]([A-Z])?(\d+)", part)
        if span:
            ids.extend(f"{span[1]}{n}" for n in range(int(span[2]), int(span[4]) + 1))
        elif re.fullmatch(r"[A-Z]\d+", part):
            ids.append(part)
    return ids


def outcomes(junit_xml: Path) -> list[Outcome]:
    """Every test in pytest's JUnit results."""
    tree = ElementTree.parse(junit_xml)  # noqa: S314 (our own test run's file)
    found: list[Outcome] = []
    for case in tree.iter("testcase"):
        tags = {child.tag for child in case}
        result: Result = (
            "failed" if tags & {"failure", "error"} else "skipped" if "skipped" in tags else "passed"
        )
        found.append(Outcome(f"{case.get('classname', '')}::{case.get('name', '')}", result))
    return found


def build(spec: str, architecture: str, results: list[Outcome]) -> list[Row]:
    plan = milestones(architecture)
    rows: list[Row] = []
    for criterion, text in criteria(spec):
        milestone = next((m for m in plan if criterion in m.ids), None)
        prefix = f"test_{criterion.lower()}_"
        # A skipped test neither proves nor fails a criterion.
        own = [t for t in results if t.name.split("::")[-1].startswith(prefix) and t.result != "skipped"]
        status: Status
        if any(t.result == "failed" for t in own):
            status = "failing"
        elif milestone is None or not milestone.done:
            status = "not yet due"
        elif not own:
            status = "missing"
        else:
            status = "proven"
        rows.append(Row(criterion, text, milestone.name if milestone else "", own, status))
    return rows


def gaps(rows: list[Row]) -> list[str]:
    """What fails the build: a criterion in no milestone, or a finished
    milestone's criterion without a passing test."""
    found: list[str] = []
    for row in rows:
        if row.milestone == "":
            found.append(f"{row.id}: in no milestone")
        elif row.status == "missing":
            found.append(f"{row.id} ({row.milestone}): no test")
        elif row.status == "failing":
            found.append(f"{row.id} ({row.milestone}): a test failed")
    return found


def html(rows: list[Row], commit: str) -> str:
    proven = sum(1 for row in rows if row.status == "proven")
    body = "\n".join(
        f"<tr><td><b>{escape(row.id)}</b> {escape(row.text)}</td><td>{escape(row.milestone)}</td>"
        f"<td>{'<br>'.join(('✓ ' if t.passed else '✗ ') + escape(t.name) for t in row.tests)}</td>"
        f"<td>{row.status}</td></tr>"
        for row in rows
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evidence pack</title><style>body{{font:16px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:72rem;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ccc;padding:.4rem;text-align:left;vertical-align:top}}</style></head><body>
<h1>Evidence pack</h1>
<p>Record Access Audit, commit <code>{escape(commit)}</code>. {proven} of {len(rows)} acceptance criteria proven. Made-up clinic, made-up staff and patients.</p>
<table>
<tr><th>Criterion</th><th>Milestone</th><th>Tests</th><th>Status</th></tr>
{body}
</table>
</body></html>
"""
