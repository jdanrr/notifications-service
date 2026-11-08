"""Puerto: envío de correos. Implementado por el adaptador SES."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EmailAttachment:
    """Adjunto del correo (ej. PDF descargado de S3)."""

    filename: str
    content: bytes
    content_type: str = "application/pdf"


@runtime_checkable
class EmailSenderPort(Protocol):
    def send(
        self,
        *,
        subject: str,
        html: str,
        text: str,
        to: str,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        """Envía un correo con versión HTML y versión texto plano.

        `attachments` es opcional para no romper los casos de uso sin
        adjuntos; solo Documents lo usa por ahora.
        """
        ...
