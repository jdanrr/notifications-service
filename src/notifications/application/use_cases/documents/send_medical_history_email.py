"""Caso de uso: enviar el PDF del historial médico adjunto al correo.

Se activa con el evento MedicalHistoryPdfGenerated.

Reglas aplicadas aquí:
- Idempotencia por eventId (SQS entrega al menos una vez): si ya se envio,
  no se vuelve a enviar ni se vuelve a descargar el PDF.
- Solo se registra el envio exitoso; el registro de fallos lo hace el worker
  (unico punto que decide borrar el mensaje).
- Error permanente  -> se propaga (el worker registra y borra).
- Error transitorio -> se propaga sin registrar (el worker NO borra).
"""

import logging
from dataclasses import replace
from datetime import UTC, datetime

from notifications.application.commands import MedicalHistoryEmailCommand
from notifications.application.models import WelcomeBrandConfig
from notifications.application.ports.attachment_provider_port import (
    AttachmentProviderPort,
)
from notifications.application.ports.email_sender_port import EmailSenderPort
from notifications.application.ports.notification_log_repository_port import (
    NotificationLogRepositoryPort,
)
from notifications.application.ports.template_renderer_port import TemplateRendererPort
from notifications.domain.errors import PermanentNotificationError
from notifications.domain.notification_log import NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)

CHANNEL = "email"
TEMPLATE_NAME = "medical_history"
HTML_TEMPLATE = "documents/medical_history.html.j2"
TEXT_TEMPLATE = "documents/medical_history.txt.j2"
SUBJECT_TEMPLATE = "Tu historial médico está listo"


class SendMedicalHistoryEmailUseCase:
    def __init__(
        self,
        renderer: TemplateRendererPort,
        sender: EmailSenderPort,
        repository: NotificationLogRepositoryPort,
        brand: WelcomeBrandConfig,
        attachments: AttachmentProviderPort,
    ) -> None:
        self._renderer = renderer
        self._sender = sender
        self._repository = repository
        self._brand = brand
        self._attachments = attachments

    def execute(self, command: MedicalHistoryEmailCommand) -> str:
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

        # La descarga va ANTES del render: si S3 falla de forma transitoria
        # el mensaje se reintenta sin dejar traza de fallo.
        downloaded = self._attachments.fetch(bucket=command.bucket, key=command.key)
        attachment = replace(downloaded, filename=command.file_name)

        context = {
            "user_name": command.user_name,
            "file_name": command.file_name,
            "generated_at": command.generated_at,
            "app_name": self._brand.app_name,
            "portal_url": self._brand.portal_url,
            "support_email": self._brand.support_email,
            "logo_url": self._brand.logo_url,
            "current_year": datetime.now(UTC).year,
        }
        subject = SUBJECT_TEMPLATE

        html = self._renderer.render(HTML_TEMPLATE, context)
        text = self._renderer.render(TEXT_TEMPLATE, context)
        self._sender.send(subject=subject, html=html, text=text, to=email, attachments=[attachment])

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
