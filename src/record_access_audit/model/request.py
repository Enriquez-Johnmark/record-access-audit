"""What the model is asked (C1): the instructions and one case's numbered
facts. Nothing else about the case, the clinic or anyone in it."""

import json
from dataclasses import dataclass

MODEL = "claude-sonnet-5-5"

SYSTEM = """You help a clinic's privacy officer review one flagged case from the record system's access log. \
Code has written the case's numbered facts. Write a short, neutral account of what the facts show, \
for the privacy officer to read before they decide.

Rules:
- Use only the facts. Every sentence lists the numbers of the facts it rests on.
- Copy times, dates, IDs and numbers exactly as the facts give them. Do not count, add up or work out \
anything the facts do not state.
- Describe; never decide or accuse. Do not say anyone did wrong, broke a rule or a law, snooped, or \
should be disciplined, and do not call a look improper, unauthorized, inappropriate or suspicious. \
The privacy officer decides.
- Say nothing clinical: no conditions, medicines, tests or treatments.
- Refer to people only by their IDs, such as S-009 and P-286.
- "summary": at most 4 sentences. "to_check": up to 3 possible innocent explanations the privacy officer \
could check (for example a visit the record does not show, a shared workstation, or work for another \
department), each citing the facts it rests on.
- At most 100 words in all."""


@dataclass(frozen=True)
class SummaryRequest:
    model: str
    system: str
    facts: tuple[str, ...]

    @classmethod
    def for_facts(cls, facts: list[str], model: str = MODEL) -> "SummaryRequest":
        return cls(model, SYSTEM, tuple(facts))

    def user_message(self) -> str:
        return "Facts:\n" + "\n".join(f"{n}. {fact}" for n, fact in enumerate(self.facts, start=1))

    def to_json(self) -> str:
        return json.dumps(
            {"model": self.model, "system": self.system, "facts": list(self.facts)}, sort_keys=True
        )
