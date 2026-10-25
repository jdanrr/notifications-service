"""Conversión de Envelope a comandos de aplicación.

Es el punto donde se valida el `detail` de cada evento. Un detail inválido o
sin email es un error permanente: el mismo mensaje siempre falla igual.
"""

from datetime import UTC

from pydantic import ValidationError

from notifications.application.commands import (
    AppointmentEmailCommand,
    PasswordResetCommand,
    SendWelcomeEmailCommand,
)
from notifications.application.models import WelcomeEmailData
from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import Envelope
from notifications.infrastructure.inbound.sqs.schemas.appointments import (
    AppointmentCancelledDetail,
    AppointmentRescheduledDetail,
    AppointmentScheduledDetail,
)
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


def _appointment_command(
    envelope: Envelope, detail: AppointmentScheduledDetail, kind: str
) -> AppointmentEmailCommand:
    """Arma el comando desde un detail de Appointments ya validado."""
    data = detail.data
    appointment = data.appointment
    physician_name = appointment.physician.name if appointment.physician else None
    center = appointment.medical_center
    previous = getattr(data, "previous_appointment", None)

    return AppointmentEmailCommand(
        event_id=envelope.event_id,
        correlation_id=envelope.correlation_id,
        kind=kind,
        user_name=data.first_name,
        email=str(data.email),
        appointment_type=appointment.type,
        date=appointment.date,
        start_time=appointment.start_time,
        weekday=appointment.weekday,
        end_time=appointment.end_time,
        physician_name=physician_name,
        medical_center_name=center.name if center else None,
        medical_center_location=center.location if center else None,
        previous_date=previous.date if previous else None,
        previous_start_time=previous.start_time if previous else None,
    )


def _validate_appointment_detail(
    envelope: Envelope, detail_cls, detail_type: str
) -> AppointmentScheduledDetail:
    try:
        return detail_cls.model_validate(envelope.detail)
    except ValidationError as exc:
        campos = ", ".join(sorted({str(err["loc"][-1]) for err in exc.errors()}))
        raise PermanentNotificationError(f"detail de {detail_type} invalido en: {campos}") from exc


def envelope_to_appointment_scheduled_command(
    envelope: Envelope,
) -> AppointmentEmailCommand:
    """Valida el detail de AppointmentScheduled y arma el comando."""
    detail = _validate_appointment_detail(
        envelope, AppointmentScheduledDetail, "AppointmentScheduled"
    )
    return _appointment_command(envelope, detail, "scheduled")


def envelope_to_appointment_rescheduled_command(
    envelope: Envelope,
) -> AppointmentEmailCommand:
    """Valida el detail de AppointmentRescheduled y arma el comando."""
    detail = _validate_appointment_detail(
        envelope, AppointmentRescheduledDetail, "AppointmentRescheduled"
    )
    return _appointment_command(envelope, detail, "rescheduled")


def envelope_to_appointment_cancelled_command(
    envelope: Envelope,
) -> AppointmentEmailCommand:
    """Valida el detail de AppointmentCancelled y arma el comando."""
    detail = _validate_appointment_detail(
        envelope, AppointmentCancelledDetail, "AppointmentCancelled"
    )
    return _appointment_command(envelope, detail, "cancelled")
