from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from tests.support.api import api, log_in
from tests.support.stored import stored

MADE = generate()


def test_a4_a_patient_sees_only_their_own_record_by_role_and_department_never_a_name(
    db: Db, db_url: str
) -> None:
    clock = stored(db)
    clinic = MADE.clinic
    # A relative at a nurse's address: their chart was opened three times, and they appear in no search list.
    label = next(
        lbl
        for lbl in MADE.labels
        if lbl.kind == "relative at the same address" and "SAME_LAST_NAME" in lbl.rules
    )
    patient = next(p for p in clinic.patients if p.id == label.patient)
    assert patient.email
    client, mail = api(db_url, clock)
    log_in(client, mail, patient.email)

    report = client.get("/api/report").json()

    opened = [a for a in clinic.accesses if a.kind.value == "chart opened" and a.patients == (patient.id,)]
    assert report["patient"] == f"{patient.given} {patient.family}"
    assert len(report["looks"]) == len(opened)
    nurse = next(s for s in clinic.staff if s.id == label.staff)
    assert {(look["role"], look["department"]) for look in report["looks"]} == {
        (nurse.role.value, nurse.department.value)
    }
    text = str(report["looks"])
    for staff in clinic.staff:
        assert staff.family not in text
        assert staff.id not in text
    assert "beyond what HIPAA now requires" in report["note"]


def test_a4_search_list_hits_and_other_patients_records_are_not_in_a_report(db: Db, db_url: str) -> None:
    clock = stored(db)
    clinic = MADE.clinic
    vip_search = next(lbl for lbl in MADE.labels if lbl.kind == "VIP in a search list only")
    patient = next(p for p in clinic.patients if p.id == vip_search.patient)
    assert patient.email
    client, mail = api(db_url, clock)
    log_in(client, mail, patient.email)
    report = client.get("/api/report").json()
    opened = [a for a in clinic.accesses if a.kind.value == "chart opened" and patient.id in a.patients]
    assert len(report["looks"]) == len(opened)
    assert all(look["at"] for look in report["looks"])


def test_a4_a_patient_cannot_reach_the_privacy_officers_pages(db: Db, db_url: str) -> None:
    clock = stored(db)
    patient = MADE.clinic.patients[0]
    assert patient.email
    client, mail = api(db_url, clock)
    log_in(client, mail, patient.email)
    assert client.get("/api/me").json() == {"who": "patient", "name": f"{patient.given} {patient.family}"}
    for path in ["/api/queue", "/api/cases/1", "/api/activity", "/api/rules"]:
        assert client.get(path).status_code in (401, 403), path
    assert client.post("/api/run").status_code in (401, 403)
