"""Caso de uso: enviar el correo cuando Appointments agenda una cita.

Se activa con el evento AppointmentScheduled.

Reglas aplicadas aquí:
- Idempotencia por eventId (SQS entrega al menos una vez): si ya se envio,
  no se vuelve a enviar.
- Solo se registra el envio exitoso; el registro de fallos lo hace el worker
  (unico punto que decide borrar el mensaje).
- Error permanente  -> se propaga (el worker registra y borra).
- Error transitorio -> se propaga sin registrar (el worker NO borra).
"""

import logging
from datetime import UTC, datetime

from notifications.application.commands import AppointmentEmailCommand
from notifications.application.models import WelcomeBrandConfig
from notifications.application.ports.email_sender_port import EmailSenderPort
from notifications.application.ports.notification_log_repository_port import (
    NotificationLogRepositoryPort,
)
from notifications.application.ports.template_renderer_port import TemplateRendererPort
from notifications.domain.errors import PermanentNotificationError
from notifications.domain.notification_log import NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)

CHANNEL = "email"
TEMPLATE_NAME = "appointment_scheduled"
HTML_TEMPLATE = "appointments/scheduled.html.j2"
TEXT_TEMPLATE = "appointments/scheduled.txt.j2"
SUBJECT_TEMPLATE = "Tu cita de {appointment_type} quedó agendada"


class SendAppointmentScheduledEmailUseCase:
    def __init__(
        self,
        renderer: TemplateRendererPort,
        sender: EmailSenderPort,
        repository: NotificationLogRepositoryPort,
        brand: WelcomeBrandConfig,
    ) -> None:
        self._renderer = renderer
        self._sender = sender
        self._repository = repository
        self._brand = brand

    def execute(self, command: AppointmentEmailCommand) -> str:
        """Devuelve 'sent' o 'duplicate'. Lanza Permanent/TransientNotificationError."""
        if self._repository.has_been_sent(command.event_id):
            logger.info(
                "evento ya procesado, se omite envio event_id=%s correlation_id=%s",
                command.event_id,
                command.correlation_id,
            )
            return "duplicate"

        email = (command.email or "").strip()
        if not email:
            raise PermanentNotificationError("falta email en el evento")

        context = {
            "user_name": command.user_name,
            "appointment_type": command.appointment_type,
            "date": command.date,
            "weekday": command.weekday,
            "start_time": command.start_time,
            "end_time": command.end_time,
            "physician_name": command.physician_name,
            "medical_center_name": command.medical_center_name,
            "medical_center_location": command.medical_center_location,
            "app_name": self._brand.app_name,
            "portal_url": self._brand.portal_url,
            "support_email": self._brand.support_email,
            "logo_url": self._brand.logo_url,
            "current_year": datetime.now(UTC).year,
        }
        subject = SUBJECT_TEMPLATE.format(appointment_type=command.appointment_type)

        html = self._renderer.render(HTML_TEMPLATE, context)
        text = self._renderer.render(TEXT_TEMPLATE, context)
        self._sender.send(subject=subject, html=html, text=text, to=email)

        self._repository.record(
            NotificationLog(
                event_id=command.event_id,
                correlation_id=command.correlation_id,
                channel=CHANNEL,
                template=TEMPLATE_NAME,
                status=NotificationStatus.SENT,
                created_at=datetime.now(UTC),
            )
        )
        logger.info(
            "correo enviado event_id=%s correlation_id=%s",
            command.event_id,
            command.correlation_id,
        )
        return "sent"
