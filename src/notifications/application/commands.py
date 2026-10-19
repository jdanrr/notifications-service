"""Comandos: peticiones que entran al layer de aplicación desde el inbound."""

from dataclasses import dataclass
from datetime import datetime

from notifications.application.models import WelcomeEmailData


@dataclass(frozen=True)
class SendWelcomeEmailCommand:
    """Envío de correo de bienvenida derivado de un evento UserRegistered."""

    event_id: str
    correlation_id: str | None
    data: WelcomeEmailData


@dataclass(frozen=True)
class PasswordResetCommand:
    """Envío del correo para restablecer contraseña (PasswordResetRequested).

    `expires_at` llega ya convertido a UTC; el caso de uso lo pasa a la zona
    horaria del usuario antes de mostrarlo.
    """

    event_id: str
    correlation_id: str | None
    user_id: str
    email: str
    first_name: str
    reset_url: str
    expires_at: datetime
