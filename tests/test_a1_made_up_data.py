import json
from datetime import timedelta
from pathlib import Path

from record_access_audit.made_up.generate import DAYS, START, generate, labels_json

ROOT = Path(__file__).resolve().parent.parent
PLANTED_KINDS = {
    "co-worker",
    "relative at the same address",
    "same last name",
    "VIP",
    "own record",
    "role that never reads charts",
    "deceased patient",
    "long after care ended",
    "burst of charts",
    "outside shift",
}


def test_a1_the_made_up_clinic_is_the_same_every_time() -> None:
    first, second = generate(), generate()
    assert first.clinic == second.clinic
    assert first.labels == second.labels


def test_a1_the_clinic_has_30_staff_300_patients_and_14_days_of_log() -> None:
    made = generate()
    clinic = made.clinic
    assert len(clinic.staff) == 30
    assert len(clinic.patients) == 300
    assert len({s.id for s in clinic.staff}) == 30
    assert len({p.id for p in clinic.patients}) == 300
    end = START + timedelta(days=DAYS)
    assert all(START <= a.at < end for a in clinic.accesses)
    assert 3500 <= len(clinic.accesses) <= 8000
    assert sorted(a.at for a in clinic.accesses) == [a.at for a in clinic.accesses]


def test_a1_every_planted_kind_and_enough_look_alikes_are_labelled() -> None:
    labels = generate().labels
    planted = [label for label in labels if label.planted]
    look_alikes = [label for label in labels if not label.planted]
    assert len(planted) >= 30
    assert len(look_alikes) >= 20
    assert {label.kind for label in planted} == PLANTED_KINDS
    assert len({label.id for label in labels}) == len(labels)


def test_a1_every_label_names_people_and_accesses_in_the_log() -> None:
    made = generate()
    staff = {s.id for s in made.clinic.staff}
    patients = {p.id for p in made.clinic.patients}
    for label in made.labels:
        assert label.staff in staff, label.id
        assert label.patient is None or label.patient in patients, label.id
        on_day = [a for a in made.clinic.accesses if a.staff == label.staff and a.at.date() == label.day]
        if label.patient is not None:
            on_day = [a for a in on_day if label.patient in a.patients]
        assert on_day, label.id


def test_a1_the_committed_labels_are_the_generated_ones() -> None:
    committed = json.loads((ROOT / "evalset" / "labels.json").read_text())
    assert committed == labels_json(generate().labels)
