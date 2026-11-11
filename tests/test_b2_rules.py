from datetime import timedelta

from record_access_audit.core.cases import CaseKey, group
from record_access_audit.core.records import Clinic
from record_access_audit.core.rules import DEFAULT_RULES, RuleCode, RuleSet, flag
from record_access_audit.made_up.generate import generate
from tests.support.clinic import (
    ANA,
    BEN,
    DAY,
    DESK,
    DOCTOR,
    GUARD,
    STAFF_RECORD,
    at,
    clinic,
    dead,
    member,
    opened,
    searched,
)


def codes(c: Clinic, access: str | None = None) -> set[RuleCode]:
    return {f.code for f in flag(c, DEFAULT_RULES) if access is None or f.access == access}


def test_b2_the_rules_flag_exactly_the_labelled_cases_with_their_rules() -> None:
    made = generate()
    found = group(flag(made.clinic, DEFAULT_RULES))
    expected = {
        CaseKey(label.staff, label.patient, None if label.patient else label.day): set(label.rules)
        for label in made.labels
        if label.rules
    }
    assert found == expected


def test_b2_every_flag_records_its_reason_code_and_rule_set_version() -> None:
    c = clinic(accesses=(opened(DOCTOR, ANA, at(10)),))
    later = RuleSet(version=7)
    flags = flag(c, later)
    assert [f.code for f in flags] == [RuleCode.NO_RELATIONSHIP]
    assert all(f.version == 7 for f in flags)


def test_b2_own_record_is_the_only_rule_on_ones_own_chart() -> None:
    assert codes(clinic(accesses=(opened(DESK, STAFF_RECORD, at(10)),))) == {RuleCode.OWN_RECORD}


def test_b2_a_role_that_never_reads_charts_is_flagged_even_when_accounted_for() -> None:
    c = clinic(
        care_teams=(member(ANA, GUARD, at(8, day=DAY - timedelta(days=9))),),
        accesses=(opened(GUARD, ANA, at(10)),),
    )
    assert codes(c) == {RuleCode.ROLE_NO_CHARTS}


def test_b2_name_address_co_worker_vip_and_death_rules_need_no_care_relationship() -> None:
    gone = dead(ANA, at(9, day=DAY - timedelta(days=3)))
    loose = clinic(
        patients=(gone, BEN, STAFF_RECORD),
        vips=frozenset({gone.id}),
        accesses=(
            opened(DOCTOR, BEN, at(10), 1),
            opened(DOCTOR, STAFF_RECORD, at(11), 2),
            opened(DOCTOR, gone, at(12), 3),
        ),
    )
    assert codes(loose, "A-00001") == {
        RuleCode.NO_RELATIONSHIP,
        RuleCode.SAME_LAST_NAME,
        RuleCode.SAME_ADDRESS,
    }
    assert codes(loose, "A-00002") == {RuleCode.NO_RELATIONSHIP, RuleCode.COWORKER}
    assert codes(loose, "A-00003") == {RuleCode.NO_RELATIONSHIP, RuleCode.VIP, RuleCode.DECEASED}
    cared = clinic(
        patients=(gone, BEN, STAFF_RECORD),
        vips=frozenset({gone.id}),
        care_teams=tuple(
            member(p, DOCTOR, at(8, day=DAY - timedelta(days=99))) for p in (gone, BEN, STAFF_RECORD)
        ),
        accesses=(opened(DOCTOR, BEN, at(10), 1), opened(DOCTOR, STAFF_RECORD, at(11), 2)),
    )
    assert codes(cared) == set()


def test_b2_care_that_ended_over_30_days_before_and_looks_off_shift_are_flagged() -> None:
    ended = member(ANA, DOCTOR, at(9, day=DAY - timedelta(days=200)), at(9, day=DAY - timedelta(days=31)))
    recent = member(ANA, DOCTOR, at(9, day=DAY - timedelta(days=200)), at(9, day=DAY - timedelta(days=29)))
    assert RuleCode.AFTER_CARE_ENDED in codes(
        clinic(care_teams=(ended,), accesses=(opened(DOCTOR, ANA, at(10)),))
    )
    assert RuleCode.AFTER_CARE_ENDED not in codes(
        clinic(care_teams=(recent,), accesses=(opened(DOCTOR, ANA, at(10)),))
    )
    assert RuleCode.OUTSIDE_SHIFT in codes(clinic(accesses=(opened(DOCTOR, ANA, at(18, 1)),)))
    assert RuleCode.OUTSIDE_SHIFT not in codes(clinic(accesses=(opened(DOCTOR, ANA, at(17, 59)),)))


def test_b2_high_volume_counts_the_patients_whose_charts_were_opened_in_a_day() -> None:
    patients = tuple(
        ANA.__class__(f"P-{n:03d}", "X", f"Fam{n}", ANA.birth_date, ANA.address, None) for n in range(10, 72)
    )
    many = tuple(opened(DOCTOR, p, at(9) + timedelta(minutes=n), n + 1) for n, p in enumerate(patients))
    cared = tuple(member(p, DOCTOR, at(8, day=DAY - timedelta(days=9))) for p in patients)
    c = clinic(patients=patients, care_teams=cared, accesses=many[:61])
    assert group(flag(c, DEFAULT_RULES)) == {CaseKey(DOCTOR.id, None, DAY): {RuleCode.HIGH_VOLUME}}
    assert flag(clinic(patients=patients, care_teams=cared, accesses=many[:60]), DEFAULT_RULES) == []


def test_b3_a_search_list_hit_never_raises_a_case() -> None:
    c = clinic(
        vips=frozenset({ANA.id}),
        accesses=(searched(DOCTOR, [ANA, BEN, STAFF_RECORD], at(23)), searched(DESK, [STAFF_RECORD], at(23))),
    )
    assert flag(c, DEFAULT_RULES) == []
