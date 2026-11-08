"""Casos de uso de AuthorizationStatusChanged y MedicalHistoryPdfGenerated (sin AWS)."""

import pytest

from notifications.application.commands import (
    AuthorizationEmailCommand,
    MedicalHistoryEmailCommand,
)
from notifications.application.use_cases.documents.send_authorization_email import (
    SendAuthorizationEmailUseCase,
)
from notifications.application.use_cases.documents.send_medical_history_email import (
    SendMedicalHistoryEmailUseCase,
)
from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.mappers import (
    envelope_to_authorization_command,
    envelope_to_medical_history_command,
)
from tests.fakes.fake_attachment_provider import FakeAttachmentProvider


def _authorization_command(**overrides) -> AuthorizationEmailCommand:
    base = dict(
        event_id="evt-auth-1",
        correlation_id="corr-1",
        user_name="Maria Fernanda",
        email="maria.gomez@example.com",
        authorization_type="MEDICAMENTOS",
        status="APROBADA",
        file_name="autorizacion_medicamentos.pdf",
        bucket="kenko-dev-documents-files",
        key="authorizations/0192b3a0-5555.pdf",
        changed_at="2026-11-02",
    )
    base.update(overrides)
    return AuthorizationEmailCommand(**base)


def _medical_history_command(**overrides) -> MedicalHistoryEmailCommand:
    base = dict(
        event_id="evt-mh-1",
        correlation_id="corr-1",
        user_name="Maria Fernanda",
        email="maria.gomez@example.com",
        file_name="historia_clinica.pdf",
        bucket="kenko-dev-documents-files",
        key="medical-history/0192b3c4.pdf",
        generated_at="2026-11-02",
    )
    base.update(overrides)
    return MedicalHistoryEmailCommand(**base)


@pytest.fixture
def authorization_use_case(renderer, fake_sender, fake_repository, brand):
    return SendAuthorizationEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
        attachments=FakeAttachmentProvider(),
    )


@pytest.fixture
def medical_history_use_case(renderer, fake_sender, fake_repository, brand):
    return SendMedicalHistoryEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
        attachments=FakeAttachmentProvider(),
    )


def test_authorization_envia_con_pdf_adjunto(authorization_use_case, fake_sender):
    assert authorization_use_case.execute(_authorization_command()) == "sent"

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu autorización de MEDICAMENTOS cambió a APROBADA"
    assert "Maria Fernanda" in sent.html
    assert "autorizacion_medicamentos.pdf" in sent.text
    assert len(sent.attachments) == 1
    assert sent.attachments[0].filename == "autorizacion_medicamentos.pdf"


def test_medical_history_envia_con_pdf_adjunto(medical_history_use_case, fake_sender):
    assert medical_history_use_case.execute(_medical_history_command()) == "sent"

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu historial médico está listo"
    assert "historia_clinica.pdf" in sent.html
    assert len(sent.attachments) == 1
    assert sent.attachments[0].filename == "historia_clinica.pdf"


def test_duplicado_no_reenvia(authorization_use_case, fake_sender):
    assert authorization_use_case.execute(_authorization_command()) == "sent"
    assert authorization_use_case.execute(_authorization_command()) == "duplicate"
    assert len(fake_sender.sent) == 1


def test_sin_email_es_permanente(authorization_use_case, medical_history_use_case):
    with pytest.raises(PermanentNotificationError):
        authorization_use_case.execute(_authorization_command(email=""))
    with pytest.raises(PermanentNotificationError):
        medical_history_use_case.execute(_medical_history_command(email=""))


def test_mapper_authorization(authorization_envelope):
    command = envelope_to_authorization_command(authorization_envelope)

    assert command.user_name == "Maria Fernanda"
    assert command.authorization_type == "MEDICAMENTOS"
    assert command.status == "APROBADA"
    assert command.file_name == "autorizacion_medicamentos.pdf"
    assert command.bucket == "kenko-dev-documents-files"


def test_mapper_medical_history(medical_history_envelope):
    command = envelope_to_medical_history_command(medical_history_envelope)

    assert command.user_name == "Maria Fernanda"
    assert command.file_name == "historia_clinica.pdf"
    assert command.generated_at == "2026-11-02"


def test_mapper_sin_status_es_permanente(authorization_envelope):
    detail = dict(authorization_envelope.detail)
    data = {**detail["data"]}
    data.pop("status")
    envelope = authorization_envelope.__class__(
        **{**authorization_envelope.__dict__, "detail": {**detail, "data": data}}
    )

    with pytest.raises(PermanentNotificationError):
        envelope_to_authorization_command(envelope)
