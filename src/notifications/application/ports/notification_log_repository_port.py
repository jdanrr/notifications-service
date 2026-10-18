"""Puerto: registro de notificaciones. Base de la idempotencia (event_id)."""

from typing import Protocol, runtime_checkable

from notifications.domain.notification_log import NotificationLog


@runtime_checkable
class NotificationLogRepositoryPort(Protocol):
    def has_been_sent(self, event_id: str) -> bool:
        """True si ese eventId ya produjo un correo enviado con éxito."""
        ...

    def record(self, log: NotificationLog) -> None:
        """Registra el resultado de un envío (sent o failed)."""
        ...
