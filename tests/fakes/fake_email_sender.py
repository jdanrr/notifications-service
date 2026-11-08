"""Fake del puerto EmailSenderPort: guarda los correos en memoria."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from notifications.application.ports.email_sender_port import EmailAttachment


@dataclass
class SentEmail:
    subject: str
    html: str
    text: str
    to: str
    attachments: Sequence[EmailAttachment] = field(default_factory=tuple)


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[SentEmail] = []
        self.error: Exception | None = None

    def send(
        self,
        *,
        subject: str,
        html: str,
        text: str,
        to: str,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(
            SentEmail(
                subject=subject,
                html=html,
                text=text,
                to=to,
                attachments=tuple(attachments),
            )
        )
