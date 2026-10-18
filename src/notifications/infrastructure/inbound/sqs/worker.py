"""Worker: loop de consumo con apagado ordenado (SIGTERM via Event en main).

Politica de borrado del mensaje:

- Exitoso o duplicado   -> se registra (si aplica) y se borra.
- Fallo permanente      -> se registra en notification_log y se borra.
- Fallo transitorio     -> NO se registra y NO se borra; SQS reintenta y, al
                           agotar reintentos (maxReceiveCount), va a la DLQ.
- Error inesperado      -> mismo tratamiento que transitorio (mas seguro).
"""

import logging
from datetime import UTC, datetime
from threading import Event

from botocore.exceptions import BotoCoreError, ClientError

from notifications.application.ports.notification_log_repository_port import (
    NotificationLogRepositoryPort,
)
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.domain.notification_log import NotificationLog, NotificationStatus
from notifications.infrastructure.inbound.sqs.envelope import Envelope, parse_envelope
from notifications.infrastructure.inbound.sqs.poller import SqsPoller, _is_permanent
from notifications.infrastructure.inbound.sqs.router import EventRouter

logger = logging.getLogger(__name__)


class AuthEventsWorker:
    def __init__(
        self,
        poller: SqsPoller,
        router: EventRouter,
        repository: NotificationLogRepositoryPort,
        template_name: str = "welcome",
        channel: str = "email",
    ) -> None:
        self._poller = poller
        self._router = router
        self._repository = repository
        self._template_name = template_name
        self._channel = channel
        self._stop = Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        logger.info("worker iniciado")
        while not self._stop.is_set():
            try:
                messages = self._poller.receive()
            except (ClientError, BotoCoreError) as exc:
                logger.error("error al recibir mensajes: %s (se reintenta)", type(exc).__name__)
                # Backoff corto para no martillar la cola si AWS esta caido.
                self._stop.wait(1.0)
                continue

            for message in messages:
                if self._stop.is_set():
                    break
                self._process(message)
        logger.info("worker detenido")

    def _process(self, message) -> None:
        try:
            envelope = parse_envelope(message.body)
        except PermanentNotificationError as exc:
            # Sin event_id fiable no hay nada que registrar; se borra para no
            # llenar la cola con un body corrupto que nunca se arregla.
            logger.warning("sobre invalido, se descarta: %s", str(exc))
            self._delete(message)
            return

        try:
            outcome = self._router.dispatch(envelope)
        except PermanentNotificationError as exc:
            logger.warning(
                "fallo permanente event_id=%s correlation_id=%s: %s",
                envelope.event_id,
                envelope.correlation_id,
                str(exc),
            )
            if self._record(envelope, NotificationStatus.FAILED):
                self._delete(message)
        except TransientNotificationError as exc:
            logger.warning(
                "fallo transitorio, NO se borra event_id=%s correlation_id=%s: %s",
                envelope.event_id,
                envelope.correlation_id,
                str(exc),
            )
        except Exception:
            logger.exception(
                "error inesperado, NO se borra event_id=%s correlation_id=%s",
                envelope.event_id,
                envelope.correlation_id,
            )
        else:
            logger.info(
                "procesado event_id=%s correlation_id=%s resultado=%s",
                envelope.event_id,
                envelope.correlation_id,
                outcome,
            )
            self._delete(message)

    def _record(self, envelope: Envelope, status: str) -> bool:
        """Registra el resultado. False => no borrar (no pudimos dejar la traza)."""
        try:
            self._repository.record(
                NotificationLog(
                    event_id=envelope.event_id,
                    correlation_id=envelope.correlation_id,
                    channel=self._channel,
                    template=self._template_name,
                    status=status,
                    created_at=datetime.now(UTC),
                )
            )
            return True
        except Exception:
            logger.exception(
                "no se pudo registrar el fallo, NO se borra event_id=%s",
                envelope.event_id,
            )
            return False

    def _delete(self, message) -> None:
        try:
            self._poller.delete(message.receipt_handle)
        except (ClientError, BotoCoreError) as exc:
            if _is_permanent(exc):
                logger.warning("no se pudo borrar mensaje: %s", type(exc).__name__)
                return
            # Se reentrega y la idempotencia por event_id evita el doble envio.
            logger.warning("fallo transitorio al borrar, se reentregara: %s", type(exc).__name__)
