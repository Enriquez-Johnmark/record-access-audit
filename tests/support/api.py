"""The API on a test database, with a mailer that keeps what it sends."""

import re
from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from record_access_audit.api.app import AppConfig, create_app
from record_access_audit.clock import Clock
from record_access_audit.made_up.generate import generate
from record_access_audit.model.client import Summariser

BASE = "http://testserver"


@dataclass
class KeptMail:
    sent: list[tuple[str, str, str]] = field(default_factory=lambda: [])

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))

    def link_for(self, to: str) -> str:
        body = next(b for t, _, b in reversed(self.sent) if t == to)
        found = re.search(r"https?://\S+/login/\S+", body)
        assert found is not None
        return found.group(0).removeprefix(BASE)


def api(db_url: str, clock: Clock, model: Summariser | None = None) -> tuple[TestClient, KeptMail]:
    mail = KeptMail()
    config = AppConfig(
        database_url=db_url,
        base_url=BASE,
        facts=generate().clinic.facts,
        fhir_url="http://127.0.0.1:8090/fhir",
    )
    app = create_app(config, clock=clock, mailer=mail, model=model)
    return TestClient(app, base_url=BASE, follow_redirects=False), mail


def log_in(client: TestClient, mail: KeptMail, email: str) -> None:
    assert client.post("/api/login", json={"email": email}).status_code == 204
    response = client.post("/api" + mail.link_for(email))
    assert response.status_code == 200
