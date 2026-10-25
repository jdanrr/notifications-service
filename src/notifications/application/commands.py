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


@dataclass(frozen=True)
class AppointmentEmailCommand:
    """Envío del correo de una cita (agendada, reprogramada o cancelada).

    Un solo comando para los tres eventos: `kind` dice cuál (`scheduled`,
    `rescheduled` o `cancelled`) y los campos opcionales solo vienen en el
    evento que los trae (cita anterior en reprogramada, etc.).
    """

    event_id: str
    correlation_id: str | None
    kind: str
    user_name: str
    email: str
    appointment_type: str
    date: str
    start_time: str
    weekday: str | None = None
    end_time: str | None = None
    physician_name: str | None = None
    medical_center_name: str | None = None
    medical_center_location: str | None = None
    previous_date: str | None = None
    previous_start_time: str | None = None
