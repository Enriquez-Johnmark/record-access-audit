from datetime import timedelta

from record_access_audit.audit_run import run_rules
from record_access_audit.made_up.generate import generate
from record_access_audit.store.db import Db
from tests.support.api import api, log_in
from tests.support.people import ADMIN_EMAIL, OFFICER_EMAIL, officer_and_admin
from tests.support.stored import stored

FACTS = generate().clinic.facts


def test_h1_a_login_link_works_once_and_only_for_15_minutes(db: Db, db_url: str) -> None:
    clock = stored(db)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    assert client.post("/api/login", json={"email": OFFICER_EMAIL.upper()}).status_code == 204
    link = mail.link_for(OFFICER_EMAIL)
    assert link.startswith("/login/")
    # Opening the link uses nothing; only the page's button (a POST) does.
    client.get(link)
    first = client.post("/api" + link)
    assert first.status_code == 200
    assert first.json() == {"who": "user"}
    assert "raa_session" in first.cookies
    assert client.get("/api/me").json()["email"] == OFFICER_EMAIL
    client.cookies.clear()
    again = client.post("/api" + link)
    assert again.status_code == 400
    assert "expired or has already been used" in again.json()["detail"]
    client.post("/api/login", json={"email": OFFICER_EMAIL})
    late = mail.link_for(OFFICER_EMAIL)
    clock.at += timedelta(minutes=16)
    assert client.post("/api" + late).status_code == 400


def test_h1_the_login_form_says_the_same_whether_or_not_the_address_is_known(db: Db, db_url: str) -> None:
    clock = stored(db)
    client, mail = api(db_url, clock)
    assert client.post("/api/login", json={"email": "nobody@example.test"}).status_code == 204
    assert mail.sent == []


def test_h1_every_staff_api_needs_a_login_and_the_right_role(db: Db, db_url: str) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    officer_only = [
        ("GET", "/api/queue"),
        ("GET", "/api/decided"),
        ("GET", "/api/cases/1"),
        ("POST", "/api/cases/1/decisions"),
        ("POST", "/api/rules"),
    ]
    admin_only = [("POST", "/api/run")]
    either = [("GET", "/api/rules"), ("GET", "/api/activity"), ("GET", "/api/me")]
    for method, path in officer_only + admin_only + either:
        assert client.request(method, path, json={}).status_code == 401, path
    log_in(client, mail, ADMIN_EMAIL)
    for method, path in officer_only:
        assert client.request(method, path, json={}).status_code == 403, path
    for method, path in either:
        assert client.request(method, path).status_code == 200, path
    client.cookies.clear()
    log_in(client, mail, OFFICER_EMAIL)
    for method, path in admin_only:
        assert client.request(method, path, json={}).status_code == 403, path
    assert client.get("/api/queue").status_code == 200


def test_h1_a_change_from_another_site_is_refused(db: Db, db_url: str) -> None:
    clock = stored(db)
    run_rules(db, clock, FACTS)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, OFFICER_EMAIL)
    response = client.post(
        "/api/cases/1/decisions",
        json={"outcome": "appropriate", "reason": "Reviewed and fine."},
        headers={"Origin": "https://elsewhere.example.test"},
    )
    assert response.status_code == 403
    assert client.get("/api/cases/1").json()["decisions"] == []


def test_h1_logging_out_ends_the_session(db: Db, db_url: str) -> None:
    clock = stored(db)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, OFFICER_EMAIL)
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


class BrokenMail:
    def send(self, to: str, subject: str, body: str) -> None:
        raise RuntimeError("the mail server is down")


def test_h1_the_link_is_sent_after_the_answer_so_a_mail_failure_changes_nothing(db: Db, db_url: str) -> None:
    from fastapi.testclient import TestClient

    from record_access_audit.api.app import AppConfig, create_app

    clock = stored(db)
    officer_and_admin(db)
    config = AppConfig(
        database_url=db_url, base_url="http://testserver", facts=FACTS, fhir_url="http://127.0.0.1:8090/fhir"
    )
    client = TestClient(create_app(config, clock=clock, mailer=BrokenMail()), base_url="http://testserver")
    assert client.post("/api/login", json={"email": OFFICER_EMAIL}).status_code == 204
    assert client.post("/api/login", json={"email": "nobody@example.test"}).status_code == 204


def test_h1_deciding_a_case_that_does_not_exist_is_not_found(db: Db, db_url: str) -> None:
    clock = stored(db)
    officer_and_admin(db)
    client, mail = api(db_url, clock)
    log_in(client, mail, OFFICER_EMAIL)
    missing = client.post(
        "/api/cases/999999/decisions", json={"outcome": "appropriate", "reason": "Checked and fine."}
    )
    assert missing.status_code == 404


def test_h1_an_unreachable_fhir_server_is_named_when_the_log_is_read(db: Db, db_url: str) -> None:
    from fastapi.testclient import TestClient

    from record_access_audit.api.app import AppConfig, create_app
    from tests.support.api import KeptMail

    clock = stored(db)
    officer_and_admin(db)
    mail = KeptMail()
    config = AppConfig(
        database_url=db_url, base_url="http://testserver", facts=FACTS, fhir_url="http://127.0.0.1:9/fhir"
    )
    client = TestClient(create_app(config, clock=clock, mailer=mail), base_url="http://testserver")
    log_in(client, mail, ADMIN_EMAIL)
    run = client.post("/api/run")
    assert run.status_code == 502
    assert "FHIR server" in run.json()["detail"]
