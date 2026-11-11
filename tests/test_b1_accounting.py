from datetime import timedelta

from record_access_audit.core.accounting import Index, Reason, reasons
from record_access_audit.core.records import Access, Clinic, Encounter
from record_access_audit.core.rules import DEFAULT_RULES, ONLY_UNACCOUNTED, flag
from record_access_audit.made_up.generate import generate
from tests.support.clinic import ANA, CLERK, DAY, DESK, DOCTOR, at, booking, clinic, member, opened, visit


def why(c: Clinic, access: Access) -> list[Reason]:
    return reasons(Index(c, DEFAULT_RULES), access.staff, access.patients[0], access.at)


def test_b1_a_care_team_member_is_accounted_for_while_on_the_team() -> None:
    c = clinic(
        care_teams=(
            member(ANA, DOCTOR, at(9, day=DAY - timedelta(days=400)), at(9, day=DAY + timedelta(days=1))),
        )
    )
    assert why(c, opened(DOCTOR, ANA, at(10))) == [Reason.CARE_TEAM]
    assert why(c, opened(DOCTOR, ANA, at(10, day=DAY + timedelta(days=2)))) == []


def test_b1_a_visit_accounts_for_that_day_and_the_days_either_side() -> None:
    c = clinic(encounters=(visit(ANA, DOCTOR, at(9)),))
    for days in (-1, 0, 1):
        assert why(c, opened(DOCTOR, ANA, at(15, day=DAY + timedelta(days=days)))) == [Reason.ENCOUNTER]
    assert why(c, opened(DOCTOR, ANA, at(15, day=DAY + timedelta(days=2)))) == []
    assert why(c, opened(DESK, ANA, at(15))) == []


def test_b1_an_appointment_accounts_for_that_day_only() -> None:
    c = clinic(appointments=(booking(ANA, DOCTOR, at(9)),))
    assert why(c, opened(DOCTOR, ANA, at(16))) == [Reason.APPOINTMENT]
    assert why(c, opened(DOCTOR, ANA, at(16, day=DAY + timedelta(days=1)))) == []


def test_b1_the_front_desk_is_accounted_for_within_14_days_of_any_booking() -> None:
    c = clinic(appointments=(booking(ANA, DOCTOR, at(9, day=DAY + timedelta(days=14))),))
    assert why(c, opened(DESK, ANA, at(10))) == [Reason.FRONT_DESK_BOOKING]
    assert why(c, opened(DESK, ANA, at(10, day=DAY - timedelta(days=1)))) == []
    assert why(c, opened(CLERK, ANA, at(10))) == []


def test_b1_billing_is_accounted_for_within_90_days_after_a_visit() -> None:
    c = clinic(encounters=(visit(ANA, DOCTOR, at(9, day=DAY - timedelta(days=90))),))
    assert why(c, opened(CLERK, ANA, at(9))) == [Reason.BILLING_VISIT]
    assert why(c, opened(CLERK, ANA, at(10))) == []
    assert why(c, opened(DESK, ANA, at(9))) == []


def test_b1_no_access_accounted_for_in_the_made_up_log_raises_an_unaccounted_only_rule() -> None:
    made = generate().clinic
    index = Index(made, DEFAULT_RULES)
    accounted = {
        a.id
        for a in made.accesses
        if a.kind.value == "chart opened" and reasons(index, a.staff, a.patients[0], a.at)
    }
    assert len(accounted) > 3000
    for f in flag(made, DEFAULT_RULES):
        if f.access in accounted:
            assert f.code not in ONLY_UNACCOUNTED, f


def test_b1_a_visit_lasting_several_days_accounts_for_every_day_of_it() -> None:
    long_visit = Encounter("E-0009", ANA.id, (DOCTOR.id,), at(23, 30), at(8, day=DAY + timedelta(days=2)))
    c = clinic(encounters=(long_visit,))
    assert why(c, opened(DOCTOR, ANA, at(7, day=DAY + timedelta(days=2)))) == [Reason.ENCOUNTER]
    assert why(c, opened(DOCTOR, ANA, at(7, day=DAY + timedelta(days=3)))) == [Reason.ENCOUNTER]
    assert why(c, opened(DOCTOR, ANA, at(7, day=DAY + timedelta(days=4)))) == []
