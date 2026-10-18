"""Puerto: envío de correos. Implementado por el adaptador SES."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailSenderPort(Protocol):
    def send(self, *, subject: str, html: str, text: str, to: str) -> None:
        """Envía un correo con versión HTML y versión texto plano."""
        ...
