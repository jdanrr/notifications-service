"""Caso de uso: enviar el correo para restablecer contraseña.

Se activa con el evento PasswordResetRequested de Authentication.

Reglas:
- Si `expires_at` ya vencio, NO se envia nada: se propaga un error permanente
  con motivo "expired" (el worker lo registra como failed y borra el mensaje).
- El enlace llega completo en el evento; aqui no se construye ni se modifica.
- `expires_at` viaja en UTC y se muestra en hora de Colombia.
- Solo se registra el envio exitoso; los fallos los registra el worker.
"""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from notifications.application.commands import PasswordResetCommand
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
NOTIFICATION_TYPE = "PASSWORD_RESET"
TEMPLATE_NAME = "password_reset"
HTML_TEMPLATE = "auth/password_reset.html.j2"
TEXT_TEMPLATE = "auth/password_reset.txt.j2"
SUBJECT_TEMPLATE = "Restablece tu contraseña de {app_name}"

# Hora local del usuario, sin depender del locale del servidor.
USER_TIMEZONE = ZoneInfo("America/Bogota")
EXPIRES_AT_FORMAT = "%d/%m/%Y %H:%M"


class SendPasswordResetEmailUseCase:
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

    def execute(self, command: PasswordResetCommand) -> str:
        """Devuelve 'sent'. Lanza Permanent/TransientNotificationError."""
        if datetime.now(UTC) >= command.expires_at:
            # Enlace vencido: reintentar no lo desvence, es permanente.
            logger.warning(
                "enlace de restablecimiento vencido event_id=%s correlation_id=%s",
                command.event_id,
                command.correlation_id,
            )
            raise PermanentNotificationError("expired")

        context = {
            "first_name": command.first_name,
            "reset_url": command.reset_url,
            "expires_at": self._format_expires_at(command.expires_at),
            "app_name": self._brand.app_name,
            "portal_url": self._brand.portal_url,
            "support_email": self._brand.support_email,
            "logo_url": self._brand.logo_url,
            "current_year": datetime.now(UTC).year,
        }
        subject = SUBJECT_TEMPLATE.format(app_name=self._brand.app_name)

        html = self._renderer.render(HTML_TEMPLATE, context)
        text = self._renderer.render(TEXT_TEMPLATE, context)
        self._sender.send(subject=subject, html=html, text=text, to=command.email)

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
            "%s enviado event_id=%s correlation_id=%s",
            NOTIFICATION_TYPE,
            command.event_id,
            command.correlation_id,
        )
        return "sent"

    @staticmethod
    def _format_expires_at(expires_at: datetime) -> str:
        """UTC -> America/Bogota en dd/mm/YYYY HH:MM (24 horas)."""
        return expires_at.astimezone(USER_TIMEZONE).strftime(EXPIRES_AT_FORMAT)
