import json

from record_access_audit.audit_run import run_rules
from record_access_audit.made_up.generate import generate
from record_access_audit.model.client import NotRecordedError
from record_access_audit.model.request import MODEL, SummaryRequest
from record_access_audit.store.db import Db
from record_access_audit.store.queue import open_cases
from record_access_audit.summaries import facts_for_case, latest_summary, summarise_open
from tests.support.stored import stored

FACTS = generate().clinic.facts
GOOD = json.dumps({"summary": [{"text": "The case's facts are listed.", "facts": [1]}], "to_check": []})


class Fake:
    model = MODEL

    def __init__(self, raw: str = GOOD) -> None:
        self.raw = raw
        self.asked: list[SummaryRequest] = []

    def answer(self, request: SummaryRequest) -> str:
        self.asked.append(request)
        return self.raw


def first_case(db: Db) -> int:
    row = db.execute("select id from cases order by id limit 1").fetchone()
    assert row is not None
    return int(row["id"])  # type: ignore[arg-type]


def test_c1_the_model_sees_only_the_cases_numbered_facts_and_each_summary_records_model_and_facts(
    db: Db,
) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    model = Fake()
    assert summarise_open(db, clock, model, FACTS) == {"shown": 34}
    case = first_case(db)
    facts = facts_for_case(db, clock, FACTS, case)
    assert SummaryRequest.for_facts(facts) in model.asked
    stored_summary = latest_summary(db, case)
    assert stored_summary is not None
    assert (stored_summary.model, stored_summary.facts, stored_summary.status) == (MODEL, facts, "shown")
    assert summarise_open(db, clock, model, FACTS) == {}


def test_c2_an_answer_that_does_not_parse_leaves_the_case_with_its_facts_and_no_summary(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    assert summarise_open(db, clock, Fake("I think S-009 is fine."), FACTS) == {"unreadable": 34}
    case = first_case(db)
    stored_summary = latest_summary(db, case)
    assert stored_summary is not None
    assert (stored_summary.status, stored_summary.summary) == ("unreadable", None)
    assert facts_for_case(db, clock, FACTS, case)


def test_c3_with_no_model_every_case_is_still_flagged_ordered_and_shown_with_its_facts(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    assert summarise_open(db, clock, None, FACTS) == {}
    queue = open_cases(db, clock)
    assert len(queue) == 34
    assert all(facts_for_case(db, clock, FACTS, row.id) for row in queue)
    assert all(latest_summary(db, row.id) is None for row in queue)


def test_c4_a_summary_never_changes_which_cases_are_flagged_or_their_order(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    before = [(row.id, row.score, row.codes) for row in open_cases(db, clock)]
    summarise_open(db, clock, Fake(), FACTS)
    assert [(row.id, row.score, row.codes) for row in open_cases(db, clock)] == before


def test_d6_a_blocked_summary_is_kept_with_its_problems_and_the_case_shows_its_facts(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    accusing = json.dumps({"summary": [{"text": "This looks like snooping.", "facts": [1]}], "to_check": []})
    assert summarise_open(db, clock, Fake(accusing), FACTS) == {"blocked": 34}
    stored_summary = latest_summary(db, first_case(db))
    assert stored_summary is not None
    assert stored_summary.status == "blocked"
    assert stored_summary.problems == [
        {
            "check": "accuses",
            "found": "snooping",
            "where": "summary sentence 1",
            "why": "A summary describes; it never decides or accuses.",
        }
    ]


class Flaky(Fake):
    """Fails on every other request, as a missing recording or an API error would."""

    def answer(self, request: SummaryRequest) -> str:
        self.asked.append(request)
        if len(self.asked) % 2 == 0:
            raise NotRecordedError("not recorded")
        return self.raw


def test_c1_a_model_error_on_one_case_leaves_it_unsummarised_and_the_others_go_on(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    assert summarise_open(db, clock, Flaky(), FACTS) == {"shown": 17, "failed": 17}
    assert summarise_open(db, clock, Fake(), FACTS) == {"shown": 17}


def test_c1_a_case_whose_facts_changed_is_summarised_again_and_an_unreadable_answer_is_retried(
    db: Db,
) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    summarise_open(db, clock, Fake("not a summary"), FACTS)
    assert summarise_open(db, clock, Fake(), FACTS) == {"shown": 34}
    assert summarise_open(db, clock, Fake(), FACTS) == {}
    case = first_case(db)
    access = db.execute("select access from flags where case_id = %s order by id limit 1", (case,)).fetchone()
    assert access is not None
    db.execute(
        "insert into accesses (id, staff, at, kind, patients, section, seconds, workstation)"
        " select 'A-99999', staff, at + interval '1 hour', kind, patients, section, seconds, workstation"
        " from accesses where id = %s",
        (access["access"],),
    )
    run_rules(db, clock, FACTS)
    assert summarise_open(db, clock, Fake(), FACTS) == {"shown": 1}
    latest = latest_summary(db, case)
    assert latest is not None
    assert latest.facts == facts_for_case(db, clock, FACTS, case)


def test_d6_a_blocked_summary_is_not_asked_for_again_until_its_facts_change(db: Db) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    accusing = json.dumps({"summary": [{"text": "This looks like snooping.", "facts": [1]}], "to_check": []})
    summarise_open(db, clock, Fake(accusing), FACTS)
    assert summarise_open(db, clock, Fake(), FACTS) == {}
