from record_access_audit.made_up.generate import generate
from record_access_audit.store.clinic import load_clinic, save_clinic
from record_access_audit.store.db import Db


def test_h2_the_clinic_read_from_fhir_is_stored_and_loaded_back_whole(db: Db) -> None:
    clinic = generate().clinic
    assert save_clinic(db, clinic) == len(clinic.accesses)
    assert save_clinic(db, clinic) == 0
    assert load_clinic(db, clinic.facts) == clinic
