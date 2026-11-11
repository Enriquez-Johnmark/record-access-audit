"""The checks every summary must pass before a person sees it (D1 to D6). Each
problem names its check, what it found and where."""

import re
from dataclasses import dataclass
from enum import StrEnum

from record_access_audit.core.summary import Sentence, Summary

MAX_WORDS = 120


class Check(StrEnum):
    CITES_NO_FACT = "cites-no-fact"
    NOT_IN_FACTS = "not-in-facts"
    ACCUSES = "accuses"
    CLINICAL = "clinical"
    TOO_LONG = "too-long"

    @property
    def description(self) -> str:
        return {
            Check.CITES_NO_FACT: "A sentence must cite one or more of the case's facts, and no others.",
            Check.NOT_IN_FACTS: "Every number, time and ID must appear in the facts the sentence cites.",
            Check.ACCUSES: "A summary describes; it never decides or accuses.",
            Check.CLINICAL: "A summary never mentions clinical content.",
            Check.TOO_LONG: f"A summary is at most {MAX_WORDS} words in all.",
        }[self]


@dataclass(frozen=True)
class Problem:
    check: Check
    found: str
    where: str


# IDs (S-009, P-286, A-01660, also written S009), dates, times, then numbers,
# including those joined to letters (3rd, 2x).
TOKENS = re.compile(r"\b(?:[SPA]-?\d{3,5}|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|\d+(?:\.\d+)?(?:st|nd|rd|th|x)?)\b")
# "one" and "once" are left out: "no one" and "one possible reason" are not counts.
NUMBER_WORDS = {
    "twice": "2",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "dozen": "12",
}
WORDS = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.IGNORECASE)

ACCUSING = re.compile(
    r"\b(violat\w*|snoop\w*|breach\w*|unauthori[sz]ed|inappropriat\w*|improper\w*|illegal\w*|unlawful\w*"
    r"|guilt\w*|misconduct|wrongdoing|fired|firing|disciplin\w*|culprit\w*|criminal\w*|suspicious\w*"
    r"|abus\w*|prying|nosy|spying|spied|offen[cs]e\w*|punish\w*|sanction\w*|unjustified|unwarranted"
    r"|no (?:legitimate|valid|good|business|work|clinical) reason|without (?:authori[sz]ation|permission)"
    r"|not (?:permitted|allowed|authori[sz]ed)|against (?:the )?(?:policy|rules))\b",
    re.IGNORECASE,
)
CLINICAL = re.compile(
    r"\b(diagnos\w*|disease\w*|illness\w*|conditions?|symptom\w*|cancer\w*|tumou?r\w*|diabet\w*|hiv"
    r"|hepatitis|pregnan\w*|abortion\w*|depress\w*|anxiety|psychiatr\w*|mental health|addiction\w*"
    r"|overdos\w*|opioid\w*|insulin|metformin|lisinopril|statins?|antibiotic\w*|chemotherapy|prescri\w*"
    r"|doses?|dosage\w*|blood pressure|cholesterol|glucose|a1c|biops\w*|x-rays?|mri|surger\w*|infection\w*"
    r"|std|sti|hba1c|therapy|treatment\w*)\b",
    re.IGNORECASE,
)


def _normal(token: str) -> str:
    """One spelling per token: S009 -> S-009, 9:50 -> 09:50, 3rd -> 3."""
    if re.fullmatch(r"[SPA]\d+", token):
        return f"{token[0]}-{token[1:]}"
    if re.fullmatch(r"\d:\d{2}", token):
        return f"0{token}"
    return re.sub(r"(st|nd|rd|th|x)$", "", token) if token[0].isdigit() else token


def _tokens(text: str) -> set[str]:
    return {_normal(t) for t in TOKENS.findall(text)}


def _sentence(sentence: Sentence, where: str, facts: list[str], case_ids: frozenset[str]) -> list[Problem]:
    problems: list[Problem] = []
    bad = [n for n in sentence.facts if not 1 <= n <= len(facts)]
    if not sentence.facts:
        problems.append(Problem(Check.CITES_NO_FACT, sentence.text, where))
    elif bad:
        problems.append(Problem(Check.CITES_NO_FACT, f"fact {bad[0]}", where))
    else:
        # The case's own staff member and patient are its subject: naming them
        # can't point at the wrong person, whichever fact a sentence cites.
        cited: set[str] = set(case_ids)
        for n in sentence.facts:
            cited |= _tokens(facts[n - 1])
        for token in TOKENS.findall(sentence.text):
            if _normal(token) not in cited:
                problems.append(Problem(Check.NOT_IN_FACTS, token, where))
                break
        else:
            for word in WORDS.findall(sentence.text):
                if NUMBER_WORDS[word.lower()] not in cited:
                    problems.append(Problem(Check.NOT_IN_FACTS, word, where))
                    break
    accusing = ACCUSING.search(sentence.text)
    if accusing:
        problems.append(Problem(Check.ACCUSES, accusing.group(0).lower(), where))
    clinical = CLINICAL.search(sentence.text)
    if clinical:
        problems.append(Problem(Check.CLINICAL, clinical.group(0).lower(), where))
    return problems


def check(summary: Summary, facts: list[str], case_ids: frozenset[str] = frozenset()) -> list[Problem]:
    """Every problem with `summary` against the case's numbered `facts` (fact 1
    is `facts[0]`); `case_ids` are the case's own staff member and patient."""
    problems: list[Problem] = []
    for n, sentence in enumerate(summary.summary, start=1):
        problems += _sentence(sentence, f"summary sentence {n}", facts, case_ids)
    for n, sentence in enumerate(summary.to_check, start=1):
        problems += _sentence(sentence, f"to check {n}", facts, case_ids)
    words = sum(len(s.text.split()) for s in [*summary.summary, *summary.to_check])
    if words > MAX_WORDS:
        problems.append(Problem(Check.TOO_LONG, f"{words} words", "the summary"))
    return problems
