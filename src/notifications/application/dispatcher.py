"""Dispatcher: decide que pasa con cada mensaje de la cola.

Concentra dos responsabilidades que eran del worker y que aqui se pueden
probar con fakes, sin SQS ni SES reales:

1. Idempotencia: si el event_id ya produjo un envio exitoso, se descarta
   sin reintentar (SQS entrega al menos una vez).
2. Clasificacion de errores:
   - permanente  -> registrar FAILED con motivo y borrar el mensaje
   - transitorio  -> NO registrar, NO borrar (SQS reintenta y luego DLQ)
   - inesperado  -> mismo tratamiento que transitorio (mas seguro)

No conoce Envelope, Pydantic, boto3 ni Jinja: solo puertos y dominio.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from notifications.application.ports.notification_log_repository_port import (
    NotificationLogRepositoryPort,
)
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.domain.notification_log import NotificationLog, NotificationStatus

logger = logging.getLogger(__name__)

# Columna notification_log.failure_reason.
MAX_REASON_LENGTH = 64


@dataclass(frozen=True)
class DispatchResult:
    outcome: str
    delete_message: bool
    failure_reason: str | None = None


class Dispatcher:
    def __init__(
        self,
        repository: NotificationLogRepositoryPort,
        channel: str = "email",
    ) -> None:
        self._repository = repository
        self._channel = channel

    def dispatch(
        self,
        operation,
        *,
        event_id: str,
        correlation_id: str | None,
        template_name: str,
    ) -> DispatchResult:
        """Ejecuta `operation` (el caso de uso) y decide si borrar el mensaje."""
        try:
            if self._repository.has_been_sent(event_id):
                logger.info(
                    "evento ya procesado, se omite event_id=%s correlation_id=%s",
                    event_id,
                    correlation_id,
                )
                return DispatchResult(outcome="duplicate", delete_message=True)
        except Exception:
            # Sin poder consultar no hay idempotencia: no borrar para no
            # arriesgar un doble envio.
            logger.exception(
                "no se pudo consultar notification_log, NO se borra event_id=%s",
                event_id,
            )
            return DispatchResult(outcome="retry", delete_message=False)

        try:
            outcome = operation()
        except PermanentNotificationError as exc:
            reason = _truncate(str(exc))
            logger.warning(
                "fallo permanente event_id=%s correlation_id=%s motivo=%s",
                event_id,
                correlation_id,
                reason,
            )
            if self._record(event_id, correlation_id, template_name, reason):
                return DispatchResult(
                    outcome="failed",
                    delete_message=True,
                    failure_reason=reason,
                )
            # No quedo la traza: no borrar.
            return DispatchResult(outcome="retry", delete_message=False)
        except TransientNotificationError as exc:
            logger.warning(
                "fallo transitorio, NO se borra event_id=%s correlation_id=%s motivo=%s",
                event_id,
                correlation_id,
                _truncate(str(exc)),
            )
            return DispatchResult(outcome="retry", delete_message=False)
        except Exception as exc:
            logger.exception(
                "error inesperado, NO se borra event_id=%s correlation_id=%s",
                event_id,
                correlation_id,
            )
            return DispatchResult(
                outcome="retry",
                delete_message=False,
                failure_reason=_truncate(type(exc).__name__),
            )

        logger.info(
            "procesado event_id=%s correlation_id=%s resultado=%s",
            event_id,
            correlation_id,
            outcome,
        )
        return DispatchResult(outcome=outcome, delete_message=True)

    def _record(
        self,
        event_id: str,
        correlation_id: str | None,
        template_name: str,
        failure_reason: str,
    ) -> bool:
        """False => no borrar (no pudimos dejar la traza del fallo)."""
        try:
            self._repository.record(
                NotificationLog(
                    event_id=event_id,
                    correlation_id=correlation_id,
                    channel=self._channel,
                    template=template_name,
                    status=NotificationStatus.FAILED,
                    failure_reason=failure_reason,
                    created_at=datetime.now(UTC),
                )
            )
            return True
        except Exception:
            logger.exception("no se pudo registrar el fallo, NO se borra event_id=%s", event_id)
            return False


def _truncate(reason: str) -> str:
    """Encaja en notification_log.failure_reason (64 chars)."""
    return reason[:MAX_REASON_LENGTH]
