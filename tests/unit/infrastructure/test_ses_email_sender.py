"""Tests del adaptador SES con botocore Stubber: sin llamadas reales a AWS."""

import email

import boto3
import pytest
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError
from botocore.stub import Stubber

from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)
from notifications.infrastructure.outbound.email.ses_email_sender import SesEmailSender

SENDER = "kenko.salud.eps@gmail.com"
TO = "maria.gomez@example.com"
SUBJECT = "Bienvenido a Kenko"
HTML = "<html><body>Hola</body></html>"
TEXT = "Hola"
LOGO = b"\x89PNG\r\n\x1a\nlogo-falso"


def build_client() -> boto3.client:
    # Credenciales dummy: Stubber intercepta antes de cualquier llamada real.
    return boto3.client(
        "ses",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def build_sender(client) -> SesEmailSender:
    return SesEmailSender(client=client, sender=SENDER, logo=LOGO)


class CaptureClient:
    """Fake que guarda el payload crudo para inspeccionar el MIME."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send_raw_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "0001"}


def test_raw_incluye_texto_html_y_logo_por_cid():
    client = CaptureClient()
    sender = build_sender(client)

    sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)

    assert len(client.sent) == 1
    payload = client.sent[0]
    assert payload["Source"] == SENDER
    assert payload["Destinations"] == [TO]

    message = email.message_from_string(payload["RawMessage"]["Data"])
    assert message["Subject"] == SUBJECT
    assert message["To"] == TO
    assert message.get_content_type() == "multipart/related"

    parts = message.get_payload()
    alternative, image = parts[0], parts[1]
    assert alternative.get_content_type() == "multipart/alternative"

    bodies = {
        part.get_content_type(): part.get_payload(decode=True).decode("utf-8")
        for part in alternative.get_payload()
    }
    assert bodies["text/plain"] == TEXT
    assert bodies["text/html"] == HTML

    assert image.get_content_type() == "image/png"
    assert image["Content-ID"] == "<logo>"
    assert image.get_filename() == "logo.png"
    assert image.get_payload(decode=True) == LOGO


def test_message_rejected_es_permanente():
    client = build_client()
    stub = Stubber(client)
    stub.add_client_error("send_raw_email", service_error_code="MessageRejected")
    stub.activate()
    sender = build_sender(client)

    with pytest.raises(PermanentNotificationError):
        sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)


def test_throttling_es_transitorio():
    client = build_client()
    stub = Stubber(client)
    stub.add_client_error("send_raw_email", service_error_code="Throttling")
    stub.activate()
    sender = build_sender(client)

    with pytest.raises(TransientNotificationError):
        sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)


@pytest.mark.parametrize(
    "exc",
    [
        ReadTimeoutError(endpoint_url="https://email.us-east-1.amazonaws.com"),
        EndpointConnectionError(endpoint_url="https://email.us-east-1.amazonaws.com"),
    ],
    ids=["timeout", "conexion"],
)
def test_fallo_de_red_es_transitorio(exc):
    class BrokenClient:
        def send_raw_email(self, **kwargs):
            raise exc

    sender = build_sender(BrokenClient())

    with pytest.raises(TransientNotificationError):
        sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)
