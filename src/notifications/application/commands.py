"""Comandos: peticiones que entran al layer de aplicación desde el inbound."""

from dataclasses import dataclass

from notifications.application.models import WelcomeEmailData


@dataclass(frozen=True)
class SendWelcomeEmailCommand:
    """Envío de correo de bienvenida derivado de un evento UserRegistered."""

    event_id: str
    correlation_id: str | None
    data: WelcomeEmailData
