"""Fake del puerto EmailSenderPort: guarda los correos en memoria."""

from dataclasses import dataclass


@dataclass
class SentEmail:
    subject: str
    html: str
    text: str
    to: str


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[SentEmail] = []
        self.error: Exception | None = None

    def send(self, *, subject: str, html: str, text: str, to: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(SentEmail(subject=subject, html=html, text=text, to=to))
