"""Caso de uso de CertificateGenerated con puertos falsos (sin AWS)."""

import pytest

from notifications.application.commands import CertificateEmailCommand
from notifications.application.use_cases.documents.send_certificate_email import (
    SendCertificateEmailUseCase,
)
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.infrastructure.inbound.sqs.mappers import (
    envelope_to_certificate_command,
)
from tests.fakes.fake_attachment_provider import FakeAttachmentProvider


def _command(**overrides) -> CertificateEmailCommand:
    base = dict(
        event_id="evt-cert-1",
        correlation_id="corr-1",
        user_name="Maria Fernanda",
        email="maria.gomez@example.com",
        file_name="certificado_afiliacion.pdf",
        bucket="kenko-dev-documents-files",
        key="certificates/0192b3a0-4444.pdf",
        issued_at="2026-11-02",
    )
    base.update(overrides)
    return CertificateEmailCommand(**base)


@pytest.fixture
def certificate_use_case(renderer, fake_sender, fake_repository, brand):
    return SendCertificateEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
        attachments=FakeAttachmentProvider(),
    )


def test_envia_con_pdf_adjunto(certificate_use_case, fake_sender):
    assert certificate_use_case.execute(_command()) == "sent"

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu certificado de Kenko está listo"
    assert sent.to == "maria.gomez@example.com"
    assert "Maria Fernanda" in sent.html
    assert "certificado_afiliacion.pdf" in sent.html
    assert "certificado_afiliacion.pdf" in sent.text

    assert len(sent.attachments) == 1
    attachment = sent.attachments[0]
    assert attachment.filename == "certificado_afiliacion.pdf"
    assert attachment.content == b"%PDF-1.4 fake"
    assert attachment.content_type == "application/pdf"


def test_duplicado_no_descarga_ni_reenvia(renderer, fake_sender, fake_repository, brand):
    attachments = FakeAttachmentProvider()
    use_case = SendCertificateEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
        attachments=attachments,
    )
    assert use_case.execute(_command()) == "sent"
    assert use_case.execute(_command()) == "duplicate"

    assert len(fake_sender.sent) == 1
    assert len(attachments.requested) == 1


def test_sin_email_es_permanente(certificate_use_case):
    with pytest.raises(PermanentNotificationError):
        certificate_use_case.execute(_command(email="  "))


def test_s3_transitorio_no_registra(renderer, fake_sender, fake_repository, brand):
    attachments = FakeAttachmentProvider()
    attachments.error = TransientNotificationError("S3 inalcanzable: Timeout")
    use_case = SendCertificateEmailUseCase(
        renderer=renderer,
        sender=fake_sender,
        repository=fake_repository,
        brand=brand,
        attachments=attachments,
    )

    with pytest.raises(TransientNotificationError):
        use_case.execute(_command())

    assert fake_sender.sent == []
    assert fake_repository.records == []


def test_mapper_desde_envelope(certificate_envelope):
    command = envelope_to_certificate_command(certificate_envelope)

    assert command.event_id == "0192b3e0-5f11-7a22-9b33-4c5d6e7f8092"
    assert command.user_name == "Maria Fernanda"
    assert command.email == "maria.gomez@example.com"
    assert command.file_name == "certificado_afiliacion.pdf"
    assert command.bucket == "kenko-dev-documents-files"
    assert command.key == "certificates/0192b3a0-4444-7ddd-8eee-000000000004.pdf"


def test_mapper_sin_archivo_es_permanente(certificate_envelope):
    detail = dict(certificate_envelope.detail)
    detail["data"] = {**detail["data"], "file": {"bucket": "", "key": "", "fileName": ""}}
    envelope = certificate_envelope.__class__(**{**certificate_envelope.__dict__, "detail": detail})

    with pytest.raises(PermanentNotificationError):
        envelope_to_certificate_command(envelope)
