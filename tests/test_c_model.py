import json
from pathlib import Path

import pytest

from record_access_audit.model.client import (
    NotRecordedError,
    RecordedSummariser,
    RecordingSummariser,
    parse_summary,
    recording_key,
)
from record_access_audit.model.request import MODEL, SummaryRequest

FACTS = [
    "Staff member S-009's role is nurse, in Family Medicine.",
    "Rule VIP raised this case: the patient is on the clinic's VIP list.",
]
GOOD = json.dumps({"summary": [{"text": "S-009 is a nurse.", "facts": [1]}], "to_check": []})


class Live:
    model = MODEL

    def __init__(self) -> None:
        self.asked: list[SummaryRequest] = []

    def answer(self, request: SummaryRequest) -> str:
        self.asked.append(request)
        return GOOD


def test_c1_the_request_carries_only_the_model_the_instructions_and_the_numbered_facts() -> None:
    request = SummaryRequest.for_facts(FACTS)
    assert set(json.loads(request.to_json())) == {"model", "system", "facts"}
    assert request.user_message() == "Facts:\n1. " + FACTS[0] + "\n2. " + FACTS[1]
    assert request.model == "claude-sonnet-5-5"


def test_c2_an_answer_that_is_not_exactly_a_summary_is_refused() -> None:
    assert parse_summary(GOOD) is not None
    for raw in [
        "",
        "not json",
        '{"summary": []}',
        json.dumps({"summary": [{"text": "x", "facts": [1]}], "verdict": "guilty"}),
    ]:
        assert parse_summary(raw) is None


def test_c1_recorded_answers_are_replayed_by_the_exact_request_and_never_reach_a_model(
    tmp_path: Path,
) -> None:
    request = SummaryRequest.for_facts(FACTS)
    live = Live()
    recording = RecordingSummariser(live, tmp_path / "summaries.json")
    assert recording.answer(request) == GOOD
    assert recording.answer(request) == GOOD
    assert len(live.asked) == 1
    replay = RecordedSummariser.from_file(tmp_path / "summaries.json", MODEL)
    assert replay.answer(request) == GOOD
    with pytest.raises(NotRecordedError):
        replay.answer(SummaryRequest.for_facts([*FACTS, "One more fact."]))
    assert recording_key(request) != recording_key(SummaryRequest.for_facts(FACTS[:1]))
