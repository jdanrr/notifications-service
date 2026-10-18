"""Errores de dominio de Notifications.

Separan dos comportamientos del worker:

- PermanentNotificationError: reintentar no arregla nada. Se registra el
  fallo y se elimina el mensaje de SQS.
- TransientNotificationError: no se elimina el mensaje. SQS lo vuelve a
  entregar y, al agotar los reintentos, pasa a la DLQ.
"""


class NotificationError(Exception):
    """Base de todos los errores del microservicio."""


class PermanentNotificationError(NotificationError):
    """Fallo permanente: se registra y se borra el mensaje."""


class TransientNotificationError(NotificationError):
    """Fallo transitorio: el mensaje NO se borra (SQS reintenta y luego DLQ)."""


class DuplicateEventError(NotificationError):
    """El eventId ya fue procesado; no se debe reenviar el correo."""


class UnsupportedEventError(PermanentNotificationError):
    """No hay caso de uso registrado para ese (source, detail_type)."""
