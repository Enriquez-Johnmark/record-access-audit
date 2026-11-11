import re

from record_access_audit.core.cases import group
from record_access_audit.core.checks import ACCUSING, CLINICAL
from record_access_audit.core.facts import case_facts
from record_access_audit.core.rules import DEFAULT_RULES, flag
from record_access_audit.made_up.generate import generate


def all_facts() -> dict[str, list[str]]:
    clinic = generate().clinic
    flags = flag(clinic, DEFAULT_RULES)
    return {
        f"{key.staff}/{key.patient or key.day}": case_facts(
            clinic,
            DEFAULT_RULES,
            key,
            [
                f
                for f in flags
                if f.staff == key.staff
                and (
                    f.patient == key.patient
                    if key.patient
                    else f.day == key.day and f.code.value == "HIGH_VOLUME"
                )
            ],
        )
        for key in group(flags)
    }


def test_a2_no_fact_carries_a_name_address_birth_date_or_clinical_content() -> None:
    clinic = generate().clinic
    people = [*clinic.staff, *clinic.patients]
    secrets = {p.given for p in people} | {p.family for p in people} | {p.address.line for p in people}
    secrets |= {p.birth_date.isoformat() for p in clinic.patients}
    facts = all_facts()
    assert len(facts) == 34
    for case, lines in facts.items():
        text = "\n".join(lines)
        for secret in secrets:
            assert not re.search(rf"\b{re.escape(secret)}\b", text), (case, secret)
        assert not CLINICAL.search(text), (case, CLINICAL.search(text))
        assert not ACCUSING.search(text), (case, ACCUSING.search(text))


def test_a2_the_facts_say_what_happened_with_pseudonymous_ids() -> None:
    facts = all_facts()
    vip = next(lines for lines in facts.values() if any("VIP list" in line for line in lines))
    assert vip[0].startswith("Staff member S-")
    assert any(
        re.match(
            r"At 2026-\d\d-\d\d \d\d:\d\d, S-\d{3} opened P-\d{3}'s chart \(\w+\) for \d+ seconds\.", line
        )
        for line in vip
    )
    assert any(line.startswith("Rule VIP raised this case:") for line in vip)
    burst = next(lines for case, lines in facts.items() if case.startswith("S-023/"))
    assert any(re.search(r"opened the charts of \d+ different patients", line) for line in burst)
