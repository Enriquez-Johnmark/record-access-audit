"""Sending email. In development every message goes to Mailpit, a test inbox
on this computer; nothing leaves the machine."""

from typing import Protocol

import httpx


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class MailpitMailer:
    def __init__(self, base_url: str, sender: str = "privacy@clinic.example.test") -> None:
        self._url = base_url.rstrip("/") + "/api/v1/send"
        self._sender = sender

    def send(self, to: str, subject: str, body: str) -> None:
        response = httpx.post(
            self._url,
            json={"From": {"Email": self._sender}, "To": [{"Email": to}], "Subject": subject, "Text": body},
            timeout=10,
        )
        response.raise_for_status()
