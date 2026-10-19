"""Entidad de dominio que registra cada notificación procesada.

Es la base de la idempotencia: SQS entrega "al menos una vez", así que
`event_id` es la clave que evita enviar el mismo correo dos veces.
"""

from dataclasses import dataclass
from datetime import datetime


class NotificationStatus:
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True)
class NotificationLog:
    event_id: str
    correlation_id: str | None
    channel: str
    template: str
    status: str
    created_at: datetime
    # Motivo del fallo cuando status == "failed" (p. ej. "expired").
    # None en los envios exitosos.
    failure_reason: str | None = None
