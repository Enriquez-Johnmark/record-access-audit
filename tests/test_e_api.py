from record_access_audit.audit_run import run_rules
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from tests.support.api import api, log_in
from tests.support.people import ADMIN_EMAIL, OFFICER_EMAIL, officer_and_admin
from tests.support.stored import stored

FACTS = generate().clinic.facts


def test_e1_the_privacy_officer_opens_a_case_decides_it_and_it_leaves_the_queue(db: Db, db_url: str) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, OFFICER_EMAIL)
    queue = client.get("/api/queue").json()
    assert len(queue) == 34
    first = queue[0]
    case = client.get(f"/api/cases/{first['id']}").json()
    assert case["staff"]["name"]
    assert case["facts"][0].startswith("Staff member S-")
    assert case["looks"]
    assert case["status"] == "open"
    assert {o["value"] for o in case["outcomes"]} == {"appropriate", "follow-up", "possible breach"}
    short = client.post(
        f"/api/cases/{first['id']}/decisions", json={"outcome": "appropriate", "reason": "ok"}
    )
    assert short.status_code == 400
    assert "at least 10 characters" in short.json()["detail"]
    made = client.post(
        f"/api/cases/{first['id']}/decisions",
        json={"outcome": "possible breach", "reason": "No care relationship; risk assessment needed."},
    )
    assert made.status_code == 201
    assert first["id"] not in [row["id"] for row in client.get("/api/queue").json()]
    assert client.get("/api/decided").json()[0]["outcome_label"] == "Possible breach: risk assessment needed"
    again = client.get(f"/api/cases/{first['id']}").json()
    assert again["reminder"]["text"].startswith("Reminder only, not legal advice")
    assert [e["action"] for e in again["timeline"]][-1] == "case.viewed"


def test_b6_the_privacy_officer_changes_the_rules_from_the_page(db: Db, db_url: str) -> None:
    clock = stored(db)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, OFFICER_EMAIL)
    page = client.get("/api/rules").json()
    assert page["version"] == 1
    settings = page["settings"]
    changed = client.post("/api/rules", json={**settings, "high_volume_charts": 45})
    assert changed.status_code == 201
    assert changed.json()["version"] == 2
    bad = client.post("/api/rules", json={**settings, "weights": {**settings["weights"], "VIP": 0}})
    assert bad.status_code == 400
    assert client.get("/api/rules").json()["version"] == 2


def test_g3_the_administrator_reads_the_whole_log_filtered_by_step(db: Db, db_url: str) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, ADMIN_EMAIL)
    logins = client.get("/api/activity", params={"action": "login"}).json()
    assert [e["actor"] for e in logins] == [ADMIN_EMAIL]
    flagged = client.get("/api/activity", params={"action": "case.flagged"}).json()
    assert len(flagged) == 34
