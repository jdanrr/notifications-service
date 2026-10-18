"""Tests de parseo del sobre de EventBridge que llega desde SQS."""

import json

import pytest

from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import parse_envelope

EVENT_ID = "01a14cf6-20ed-7708-b1a1-681d317aa7c9"
CORRELATION_ID = "01a14cf6-20ec-759b-be6e-f8ea2482d4cd"


def test_parsea_sobre_completo(welcome_event_json):
    envelope = parse_envelope(welcome_event_json)

    assert envelope.source == "kenko.auth"
    assert envelope.detail_type == "UserRegistered"
    assert envelope.event_id == EVENT_ID
    assert envelope.correlation_id == CORRELATION_ID
    assert envelope.detail["data"]["contact"]["email"] == "maria.gomez@example.com"


def test_detail_queda_como_objeto(welcome_event):
    envelope = parse_envelope(json.dumps(welcome_event))

    assert isinstance(envelope.detail, dict)
    assert envelope.detail["data"]["person"]["firstName"] == "Maria Fernanda"


@pytest.mark.parametrize(
    "body",
    [
        "no es json",
        "[]",
        '{"source": "kenko.auth"}',
        '{"detail-type": "UserRegistered", "detail": {}}',
        '{"source": "s", "detail-type": "t", "detail": {"metadata": {}}}',
        '{"source": "s", "detail-type": "t", "detail": {"metadata": {"x": 1}}}',
    ],
    ids=["no-json", "no-objeto", "sin-detail-type", "sin-metadata", "sin-eventId", "eventId-vacio"],
)
def test_sobre_invalido_es_error_permanente(body):
    with pytest.raises(PermanentNotificationError):
        parse_envelope(body)
