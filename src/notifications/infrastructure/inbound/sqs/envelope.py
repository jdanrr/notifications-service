"""Parseo del sobre completo de EventBridge que llega como body de SQS.

No conoce los campos de negocio: solo extrae source, detail-type, eventId y
correlationId. El detalle lo validan los schemas de cada productor.
"""

import json
from dataclasses import dataclass
from typing import Any

from notifications.domain.errors import PermanentNotificationError


@dataclass(frozen=True)
class Envelope:
    source: str
    detail_type: str
    event_id: str
    correlation_id: str | None
    detail: dict[str, Any]


def parse_envelope(body: str) -> Envelope:
    """Convierte el body SQS en Envelope. Cualquier problema es permanente:
    el mismo body siempre falla igual, reintentar no lo arregla."""
    try:
        raw = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PermanentNotificationError("body no es JSON valido") from exc

    if not isinstance(raw, dict):
        raise PermanentNotificationError("sobre no es un objeto JSON")

    source = raw.get("source")
    detail_type = raw.get("detail-type")
    if not source or not detail_type:
        raise PermanentNotificationError("sobre sin source o detail-type")

    detail = raw.get("detail")
    if not isinstance(detail, dict):
        raise PermanentNotificationError("sobre sin detail")

    metadata = detail.get("metadata")
    if not isinstance(metadata, dict):
        raise PermanentNotificationError("detail sin metadata")

    event_id = metadata.get("eventId")
    if not event_id:
        raise PermanentNotificationError("detail sin metadata.eventId")

    return Envelope(
        source=source,
        detail_type=detail_type,
        event_id=event_id,
        correlation_id=metadata.get("correlationId"),
        detail=detail,
    )
