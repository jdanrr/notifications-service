"""Caso de uso de restablecimiento de contraseña con puertos falsos (sin AWS)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from notifications.application.commands import PasswordResetCommand
from notifications.application.use_cases.auth.send_password_reset_email import (
    SendPasswordResetEmailUseCase,
)
from notifications.domain.errors import PermanentNotificationError

EVENT_ID = "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e0f"
CORRELATION_ID = "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e10"
RESET_URL = "http://localhost:8080/reset#token=EXAMPLE_TOKEN"


@pytest.fixture
def command() -> PasswordResetCommand:
    # 22:15:30 UTC = 17:15:30 en America/Bogota (UTC-5).
    return PasswordResetCommand(
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        user_id="usr-1",
        email="maria.gomez@example.com",
        first_name="Maria Fernanda",
        reset_url=RESET_URL,
        expires_at=datetime(2030, 10, 18, 22, 15, 30, tzinfo=UTC),
    )


@pytest.fixture
def use_case(renderer, fake_sender, fake_repository, brand) -> SendPasswordResetEmailUseCase:
    return SendPasswordResetEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
    )


def test_envia_html_y_texto_en_un_mensajeria(use_case, fake_sender, command):
    assert use_case.execute(command) == "sent"

    assert len(fake_sender.sent) == 1
    sent = fake_sender.sent[0]
    assert sent.subject == "Restablece tu contraseña de Kenko"
    assert sent.to == "maria.gomez@example.com"


def test_contexto_con_url_nombre_y_fecha(use_case, fake_sender, command):
    use_case.execute(command)

    sent = fake_sender.sent[0]
    # El enlace llega tal cual, con el fragmento #token=.
    assert RESET_URL in sent.html
    assert RESET_URL in sent.text
    assert "Maria Fernanda" in sent.html
    assert "Maria Fernanda" in sent.text
    # 22:15:30 UTC -> 17:15:30 Bogota, formato dd/mm/YYYY HH:MM.
    assert "18/10/2030 17:15" in sent.html
    assert "18/10/2030 17:15" in sent.text


def test_conversion_a_bogota_no_depende_del_servidor(use_case, fake_sender, command):
    """Zona fija: el mismo instante UTC da siempre la misma hora local."""
    use_case.execute(command)

    manual = command.expires_at.astimezone(ZoneInfo("America/Bogota"))
    esperado = manual.strftime("%d/%m/%Y %H:%M")

    assert esperado == "18/10/2030 17:15"
    assert esperado in fake_sender.sent[0].text


def test_registra_sent_con_plantilla_correcta(use_case, fake_repository, command):
    use_case.execute(command)

    record = fake_repository.records[0]
    assert record.event_id == EVENT_ID
    assert record.template == "password_reset"
    assert record.status == "sent"
    assert record.failure_reason is None


def test_enlace_vencido_no_envia_nada(use_case, fake_sender, fake_repository):
    vencido = PasswordResetCommand(
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        user_id="usr-1",
        email="maria.gomez@example.com",
        first_name="Maria Fernanda",
        reset_url=RESET_URL,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    with pytest.raises(PermanentNotificationError) as exc:
        use_case.execute(vencido)

    assert str(exc.value) == "expired"
    assert fake_sender.sent == []
    assert fake_repository.records == []


def test_enlace_vencido_es_permanente_no_transitorio(use_case):
    vencido = PasswordResetCommand(
        event_id=EVENT_ID,
        correlation_id=CORRELATION_ID,
        user_id="usr-1",
        email="maria.gomez@example.com",
        first_name="Maria Fernanda",
        reset_url=RESET_URL,
        expires_at=datetime.now(UTC) - timedelta(days=3),
    )

    from notifications.domain.errors import TransientNotificationError

    with pytest.raises(PermanentNotificationError):
        use_case.execute(vencido)
    with pytest.raises(Exception) as exc:
        use_case.execute(vencido)
    assert not isinstance(exc.value, TransientNotificationError)


def test_fallo_permanente_de_ses_no_registra_sent(use_case, fake_sender, fake_repository, command):
    from notifications.domain.errors import PermanentNotificationError as Perm

    fake_sender.error = Perm("SES rechazo el correo: MessageRejected")

    with pytest.raises(Perm):
        use_case.execute(command)

    assert fake_sender.sent == []
    assert fake_repository.records == []


def test_fallo_transitorio_propaga_sin_registrar(use_case, fake_sender, command):
    from notifications.domain.errors import TransientNotificationError

    fake_sender.error = TransientNotificationError("SES fallo: Throttling")

    with pytest.raises(TransientNotificationError):
        use_case.execute(command)

    assert fake_sender.sent == []
