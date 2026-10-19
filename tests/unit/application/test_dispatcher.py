"""Dispatcher: idempotencia y clasificacion de errores, con fakes (sin AWS)."""

import pytest

from notifications.application.dispatcher import Dispatcher
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.domain.notification_log import NotificationStatus
from tests.fakes.in_memory_notification_log_repository import (
    InMemoryNotificationLogRepository,
)

EVENT_ID = "evt-1"
CORRELATION_ID = "corr-1"
TEMPLATE = "password_reset"


@pytest.fixture
def repository() -> InMemoryNotificationLogRepository:
    return InMemoryNotificationLogRepository()


@pytest.fixture
def dispatcher(repository) -> Dispatcher:
    return Dispatcher(repository)


def run(dispatcher, operation):
    return dispatcher.dispatch(
        operation,
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        template_name=TEMPLATE,
    )


def test_exito_se_borra_y_no_registra_fallo(dispatcher, repository):
    result = run(dispatcher, lambda: "sent")

    assert result.outcome == "sent"
    assert result.delete_message is True
    assert result.failure_reason is None
    assert repository.failures == []


def test_segunda_entrega_del_mismo_evento_no_reenvia(dispatcher, repository):
    """El caso de uso registra el envio; una segunda entrega no lo reejecuta."""
    llamadas = []

    def operation():
        llamadas.append(1)
        _y_registra(repository)
        return "sent"

    primera = run(dispatcher, operation)
    assert primera.outcome == "sent"
    assert llamadas == [1]

    segunda = run(dispatcher, operation)
    assert segunda.outcome == "duplicate"
    assert segunda.delete_message is True
    assert llamadas == [1]  # no se volvio a ejecutar el caso de uso


def _y_registra(repository) -> str:
    from datetime import UTC, datetime

    from notifications.domain.notification_log import NotificationLog

    repository.record(
        NotificationLog(
            event_id=EVENT_ID,
            correlation_id=CORRELATION_ID,
            channel="email",
            template=TEMPLATE,
            status=NotificationStatus.SENT,
            created_at=datetime.now(UTC),
        )
    )
    return "sent"


def test_error_permanente_registra_failed_y_borra(dispatcher, repository):
    def operation():
        raise PermanentNotificationError("expired")

    result = run(dispatcher, operation)

    assert result.outcome == "failed"
    assert result.delete_message is True
    assert result.failure_reason == "expired"

    assert len(repository.failures) == 1
    fallo = repository.failures[0]
    assert fallo.status == NotificationStatus.FAILED
    assert fallo.failure_reason == "expired"
    assert fallo.template == TEMPLATE
    assert fallo.event_id == EVENT_ID
    assert fallo.correlation_id == CORRELATION_ID


def test_error_transitorio_no_registra_y_no_borra(dispatcher, repository):
    def operation():
        raise TransientNotificationError("SES fallo: Throttling")

    result = run(dispatcher, operation)

    assert result.outcome == "retry"
    assert result.delete_message is False
    assert repository.records == []


def test_error_inesperado_no_registra_y_no_borra(dispatcher, repository):
    def operation():
        raise RuntimeError("algo raro")

    result = run(dispatcher, operation)

    assert result.outcome == "retry"
    assert result.delete_message is False
    assert repository.records == []


def test_si_falla_el_registro_no_se_borra(dispatcher):
    class RepositorioRoto:
        def has_been_sent(self, event_id):
            return False

        def record(self, log):
            raise RuntimeError("base de datos no disponible")

    result = Dispatcher(RepositorioRoto()).dispatch(
        lambda: (_ for _ in ()).throw(PermanentNotificationError("expired")),
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        template_name=TEMPLATE,
    )

    # Sin traza no se puede borrar: se reintenta.
    assert result.outcome == "retry"
    assert result.delete_message is False


def test_si_falla_la_consulta_de_idempotencia_no_se_borra(dispatcher):
    class RepositorioRoto:
        def has_been_sent(self, event_id):
            raise RuntimeError("base de datos no disponible")

        def record(self, log):  # pragma: no cover
            raise AssertionError("no deberia registrar")

    llamadas = []

    def operation():
        llamadas.append(1)
        return "sent"

    result = Dispatcher(RepositorioRoto()).dispatch(
        operation,
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        template_name=TEMPLATE,
    )

    assert result.outcome == "retry"
    assert result.delete_message is False
    assert llamadas == []  # no arriesga un doble envio


def test_motivo_largo_se_trunca_a_64(dispatcher, repository):
    def operation():
        raise PermanentNotificationError("x" * 200)

    result = run(dispatcher, operation)

    assert len(result.failure_reason) == 64
    assert len(repository.failures[0].failure_reason) == 64


def test_las_transitorias_no_dejan_motivo_en_log(dispatcher, repository):
    def operation():
        raise TransientNotificationError("red caida")

    run(dispatcher, operation)

    assert repository.records == []
