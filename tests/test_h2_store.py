from dataclasses import replace

from record_access_audit.core.records import Role
from record_access_audit.made_up.generate import generate
from record_access_audit.store.clinic import load_clinic, save_clinic
from record_access_audit.store.db import Db


def test_h2_the_clinic_read_from_fhir_is_stored_and_loaded_back_whole(db: Db) -> None:
    clinic = generate().clinic
    assert save_clinic(db, clinic) == len(clinic.accesses)
    assert save_clinic(db, clinic) == 0
    assert load_clinic(db, clinic.facts) == clinic


def test_h2_a_later_change_to_staff_patients_or_care_is_stored(db: Db) -> None:
    clinic = generate().clinic
    save_clinic(db, clinic)
    member = clinic.care_teams[0]
    patient = clinic.patients[1]
    staff = clinic.staff[2]
    encounter = clinic.encounters[3]
    when = clinic.accesses[-1].at
    changed = replace(
        clinic,
        care_teams=(replace(member, end=when), *clinic.care_teams[1:]),
        patients=(clinic.patients[0], replace(patient, deceased_at=when), *clinic.patients[2:]),
        staff=(*clinic.staff[:2], replace(staff, role=Role.BILLING), *clinic.staff[3:]),
        encounters=(*clinic.encounters[:3], replace(encounter, end=when), *clinic.encounters[4:]),
    )
    assert save_clinic(db, changed) == 0
    assert load_clinic(db, clinic.facts) == changed
