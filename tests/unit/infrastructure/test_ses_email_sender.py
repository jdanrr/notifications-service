"""Tests del adaptador SES con botocore Stubber: sin llamadas reales a AWS."""

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


def build_client() -> boto3.client:
    # Credenciales dummy: Stubber intercepta antes de cualquier llamada real.
    return boto3.client(
        "ses",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def add_expected_send(stub: Stubber) -> None:
    stub.add_response(
        "send_email",
        {"MessageId": "0001"},
        {
            "Source": SENDER,
            "Destination": {"ToAddresses": [TO]},
            "Message": {
                "Subject": {"Data": SUBJECT, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": HTML, "Charset": "UTF-8"},
                    "Text": {"Data": TEXT, "Charset": "UTF-8"},
                },
            },
        },
    )


def test_send_email_usa_payload_esperado():
    client = build_client()
    stub = Stubber(client)
    add_expected_send(stub)
    stub.activate()
    sender = SesEmailSender(client=client, sender=SENDER)

    sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)

    stub.assert_no_pending_responses()


def test_message_rejected_es_permanente():
    client = build_client()
    stub = Stubber(client)
    stub.add_client_error("send_email", service_error_code="MessageRejected")
    stub.activate()
    sender = SesEmailSender(client=client, sender=SENDER)

    with pytest.raises(PermanentNotificationError):
        sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)


def test_throttling_es_transitorio():
    client = build_client()
    stub = Stubber(client)
    stub.add_client_error("send_email", service_error_code="Throttling")
    stub.activate()
    sender = SesEmailSender(client=client, sender=SENDER)

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
        def send_email(self, **kwargs):
            raise exc

    sender = SesEmailSender(client=BrokenClient(), sender=SENDER)

    with pytest.raises(TransientNotificationError):
        sender.send(subject=SUBJECT, html=HTML, text=TEXT, to=TO)
