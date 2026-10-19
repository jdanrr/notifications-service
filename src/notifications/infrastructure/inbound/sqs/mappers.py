"""Conversión de Envelope a comandos de aplicación.

Es el punto donde se valida el `detail` de cada evento. Un detail inválido o
sin email es un error permanente: el mismo mensaje siempre falla igual.
"""

from datetime import UTC

from pydantic import ValidationError

from notifications.application.commands import PasswordResetCommand, SendWelcomeEmailCommand
from notifications.application.models import WelcomeEmailData
from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import Envelope
from notifications.infrastructure.inbound.sqs.schemas.auth import (
    PasswordResetRequestedDetail,
    UserRegisteredDetail,
)


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


def envelope_to_password_reset_command(envelope: Envelope) -> PasswordResetCommand:
    """Valida el detail de PasswordResetRequested y arma el comando.

    Un detail invalido (email malo, resetUrl no-http, expiresAt ausente o sin
    zona) es permanente: el mismo mensaje siempre falla igual.
    """
    try:
        detail = PasswordResetRequestedDetail.model_validate(envelope.detail)
    except ValidationError as exc:
        # Sin el input: puede contener email, token o datos personales.
        campos = ", ".join(sorted({str(err["loc"][-1]) for err in exc.errors()}))
        raise PermanentNotificationError(
            f"detail de PasswordResetRequested invalido en: {campos}"
        ) from exc

    data = detail.data

    return PasswordResetCommand(
        event_id=envelope.event_id,
        correlation_id=envelope.correlation_id,
        user_id=data.user_id,
        email=str(data.email),
        first_name=data.first_name,
        reset_url=data.reset_url,
        expires_at=data.expires_at.astimezone(UTC),
    )
