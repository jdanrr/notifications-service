"""Conversión de Envelope a comandos de aplicación.

Es el punto donde se valida el `detail` de cada evento. Un detail inválido o
sin email es un error permanente: el mismo mensaje siempre falla igual.
"""

from pydantic import ValidationError

from notifications.application.commands import SendWelcomeEmailCommand
from notifications.application.models import WelcomeEmailData
from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import Envelope
from notifications.infrastructure.inbound.sqs.schemas.auth import UserRegisteredDetail


def envelope_to_welcome_command(envelope: Envelope) -> SendWelcomeEmailCommand:
    try:
        detail = UserRegisteredDetail.model_validate(envelope.detail)
    except ValidationError as exc:
        # No se incluye el input: podria contener datos personales.
        raise PermanentNotificationError("detail de UserRegistered invalido") from exc

    email = (detail.data.contact.email or "").strip()
    if not email:
        raise PermanentNotificationError("falta contact.email en UserRegistered")

    return SendWelcomeEmailCommand(
        event_id=envelope.event_id,
        correlation_id=envelope.correlation_id,
        data=WelcomeEmailData(user_name=detail.data.person.first_name, email=email),
    )
