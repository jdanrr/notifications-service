"""Worker: loop de consumo de SQS con apagado ordenado (SIGTERM via Event).

Solo hace I/O de cola: recibir, decidir el borrado con `Dispatcher` y borrar.
La idempotencia y la clasificacion de errores viven en
`application/dispatcher.py`, donde se prueban sin SQS real.

Si el worker muere a mitad de mensaje, SQS reentrega y la idempotencia por
event_id evita el doble envio.
"""

import logging
from threading import Event

from botocore.exceptions import BotoCoreError, ClientError

from notifications.application.dispatcher import Dispatcher
from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import parse_envelope
from notifications.infrastructure.inbound.sqs.poller import SqsPoller, _is_permanent
from notifications.infrastructure.inbound.sqs.router import EventRouter

logger = logging.getLogger(__name__)

# Evento escuchado por nadie: no hay plantilla propia que reportar.
UNKNOWN_TEMPLATE = "unknown"


class EventsWorker:
    def __init__(
        self,
        poller: SqsPoller,
        router: EventRouter,
        dispatcher: Dispatcher,
    ) -> None:
        self._poller = poller
        self._router = router
        self._dispatcher = dispatcher
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

        route = self._router.route(envelope)
        # El template_name viene de la RUTA: cada evento reporta su propia
        # plantilla al registrar un fallo.
        template_name = route.template_name if route else UNKNOWN_TEMPLATE

        def operation() -> str:
            if route is None:
                from notifications.domain.errors import UnsupportedEventError

                raise UnsupportedEventError(
                    f"sin handler para {envelope.source}/{envelope.detail_type}"
                )
            return route.handler(envelope)

        result = self._dispatcher.dispatch(
            operation,
            event_id=envelope.event_id,
            correlation_id=envelope.correlation_id,
            template_name=template_name,
        )

        if result.delete_message:
            self._delete(message)

    def _delete(self, message) -> None:
        try:
            self._poller.delete(message)
        except (ClientError, BotoCoreError) as exc:
            if _is_permanent(exc):
                logger.warning("no se pudo borrar mensaje: %s", type(exc).__name__)
                return
            # Se reentrega y la idempotencia por event_id evita el doble envio.
            logger.warning("fallo transitorio al borrar, se reentregara: %s", type(exc).__name__)
