"""Tests del caso de uso de bienvenida con puertos falsos (sin AWS real)."""

import pytest

from notifications.application.commands import SendWelcomeEmailCommand
from notifications.application.models import WelcomeEmailData
from notifications.application.use_cases.auth.send_welcome_email import (
    SendWelcomeEmailUseCase,
)
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.domain.notification_log import NotificationStatus

EVENT_ID = "01a14cf6-20ed-7708-b1a1-681d317aa7c9"
CORRELATION_ID = "01a14cf6-20ec-759b-be6e-f8ea2482d4cd"


@pytest.fixture
def command() -> SendWelcomeEmailCommand:
    return SendWelcomeEmailCommand(
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        data=WelcomeEmailData(user_name="Maria Fernanda", email="maria.gomez@example.com"),
    )


@pytest.fixture
def use_case(renderer, fake_sender, fake_repository, brand) -> SendWelcomeEmailUseCase:
    return SendWelcomeEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
    )


def test_envia_correo_html_y_texto(use_case, fake_sender, fake_repository, command):
    outcome = use_case.execute(command)

    assert outcome == "sent"
    assert len(fake_sender.sent) == 1

    sent = fake_sender.sent[0]
    assert sent.subject == "Bienvenido a Kenko"
    assert sent.to == "maria.gomez@example.com"
    assert "Maria Fernanda" in sent.html
    assert "Maria Fernanda" in sent.text
    assert "<html" in sent.html
    assert "<html" not in sent.text

    assert fake_repository.records[0].status == NotificationStatus.SENT
    assert fake_repository.records[0].event_id == EVENT_ID


def test_segunda_entrega_del_mismo_evento_no_reenvia(use_case, fake_sender, command):
    assert use_case.execute(command) == "sent"
    assert use_case.execute(command) == "duplicate"

    assert len(fake_sender.sent) == 1


def test_email_vacio_es_error_permanente(use_case, fake_sender):
    command = SendWelcomeEmailCommand(
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        data=WelcomeEmailData(user_name="Maria Fernanda", email="   "),
    )

    with pytest.raises(PermanentNotificationError):
        use_case.execute(command)

    assert fake_sender.sent == []


def test_fallo_permanente_de_ses_no_registra_envio(use_case, fake_sender, fake_repository, command):
    fake_sender.error = PermanentNotificationError("SES rechazo el correo: MessageRejected")

    with pytest.raises(PermanentNotificationError):
        use_case.execute(command)

    assert fake_sender.sent == []
    assert fake_repository.records == []
    # Sin registro 'sent' => el worker podra reintentar si el evento vuelve.
    assert not fake_repository.has_been_sent(EVENT_ID)


def test_fallo_transitorio_propaga_sin_registrar(use_case, fake_sender, fake_repository, command):
    fake_sender.error = TransientNotificationError("SES fallo (reintentable): Throttling")

    with pytest.raises(TransientNotificationError):
        use_case.execute(command)

    assert fake_sender.sent == []
    assert fake_repository.records == []
