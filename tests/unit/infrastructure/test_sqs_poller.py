"""Tests del poller multi-cola con botocore Stubber: sin llamadas reales a AWS."""

import boto3
import pytest
from botocore.stub import Stubber

from notifications.infrastructure.inbound.sqs.poller import SqsMessage, SqsPoller

QUEUE_A = "https://sqs.us-east-1.amazonaws.com/137696817246/kenko-dev-notifications-authentication"
QUEUE_B = "https://sqs.us-east-1.amazonaws.com/137696817246/kenko-dev-notifications-appointments"


def build_client() -> boto3.client:
    # Credenciales dummy: Stubber intercepta antes de cualquier llamada real.
    return boto3.client(
        "sqs",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def add_empty_receive(stub: Stubber, queue_url: str) -> None:
    stub.add_response(
        "receive_message",
        {},
        {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": 1,
            "WaitTimeSeconds": 20,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        },
    )


def add_one_message(stub: Stubber, queue_url: str, body: str = "hola") -> None:
    stub.add_response(
        "receive_message",
        {"Messages": [{"ReceiptHandle": "rh-1", "Body": body}]},
        {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": 1,
            "WaitTimeSeconds": 20,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        },
    )


def test_sin_colas_falla_en_seco():
    with pytest.raises(ValueError):
        SqsPoller(client=build_client(), queue_urls=[])


def test_alterna_entre_colas_en_cada_receive():
    client = build_client()
    stub = Stubber(client)
    add_empty_receive(stub, QUEUE_A)
    add_empty_receive(stub, QUEUE_B)
    add_empty_receive(stub, QUEUE_A)
    stub.activate()

    poller = SqsPoller(client=client, queue_urls=[QUEUE_A, QUEUE_B])

    assert poller.receive() == []
    assert poller.receive() == []
    assert poller.receive() == []
    stub.assert_no_pending_responses()


def test_mensaje_recuerda_su_cola_de_origen():
    client = build_client()
    stub = Stubber(client)
    add_empty_receive(stub, QUEUE_A)
    add_one_message(stub, QUEUE_B)
    stub.activate()

    poller = SqsPoller(client=client, queue_urls=[QUEUE_A, QUEUE_B])

    assert poller.receive() == []
    assert poller.receive() == [SqsMessage(receipt_handle="rh-1", body="hola", queue_url=QUEUE_B)]
    stub.assert_no_pending_responses()


def test_borrado_va_a_la_cola_de_origen():
    client = build_client()
    stub = Stubber(client)
    stub.add_response(
        "delete_message",
        {},
        {"QueueUrl": QUEUE_B, "ReceiptHandle": "rh-1"},
    )
    stub.activate()

    poller = SqsPoller(client=client, queue_urls=[QUEUE_A, QUEUE_B])
    poller.delete(SqsMessage(receipt_handle="rh-1", body="hola", queue_url=QUEUE_B))

    stub.assert_no_pending_responses()


def test_una_sola_cola_funciona_igual_que_antes():
    client = build_client()
    stub = Stubber(client)
    add_one_message(stub, QUEUE_A)
    add_empty_receive(stub, QUEUE_A)
    stub.activate()

    poller = SqsPoller(client=client, queue_urls=[QUEUE_A])

    assert poller.receive()[0].queue_url == QUEUE_A
    assert poller.receive() == []
    stub.assert_no_pending_responses()
