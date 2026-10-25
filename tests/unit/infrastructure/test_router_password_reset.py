"""El par (source, detail_type) debe llegar al caso de uso correcto."""

import json

import pytest

import notifications.infrastructure.inbound.sqs.mappers as mappers
from notifications.application.commands import PasswordResetCommand, SendWelcomeEmailCommand
from notifications.domain.errors import UnsupportedEventError
from notifications.infrastructure.inbound.sqs.envelope import parse_envelope
from tests.unit.infrastructure.test_route_registry_sync import build_test_router


def body(source: str, detail_type: str) -> str:
    return json.dumps(
        {
            "source": source,
            "detail-type": detail_type,
            "detail": {
                "metadata": {
                    "eventId": "evt-x",
                    "eventVersion": "1",
                    "occurredAt": "2030-10-18T21:45:30.000Z",
                    "correlationId": "corr-x",
                },
                "data": {},
            },
        }
    )


def test_password_reset_llega_a_su_ruta(password_reset_envelope):
    route = build_test_router().route(password_reset_envelope)

    assert route is not None
    assert route.template_name == "password_reset"


def test_user_registered_conserva_su_ruta(welcome_envelope):
    route = build_test_router().route(welcome_envelope)

    assert route is not None
    assert route.template_name == "welcome"


def test_eventos_auth_registrados_en_el_mismo_router():
    router = build_test_router()

    assert router.registered_routes() >= {
        ("kenko.auth", "UserRegistered"),
        ("kenko.auth", "PasswordResetRequested"),
    }


def test_mapper_de_password_reset_devuelve_su_comando(password_reset_envelope):
    cmd = mappers.envelope_to_password_reset_command(password_reset_envelope)

    assert isinstance(cmd, PasswordResetCommand)
    assert cmd.event_id == password_reset_envelope.event_id
    assert cmd.correlation_id == password_reset_envelope.correlation_id
    assert cmd.email == "maria.gomez@example.com"
    assert cmd.first_name == "Maria Fernanda"
    assert cmd.reset_url == "http://localhost:8080/reset#token=EXAMPLE_TOKEN"


def test_mapper_de_welcome_conserva_su_comando(welcome_envelope):
    cmd = mappers.envelope_to_welcome_command(welcome_envelope)

    assert isinstance(cmd, SendWelcomeEmailCommand)
    assert cmd.event_id == welcome_envelope.event_id


def test_mapper_password_reset_exige_su_estructura(welcome_envelope):
    """Un UserRegistered no sirve como PasswordResetRequested."""
    from notifications.domain.errors import PermanentNotificationError

    with pytest.raises(PermanentNotificationError):
        mappers.envelope_to_password_reset_command(welcome_envelope)


def test_evento_desconocido_no_tiene_ruta():
    router = build_test_router()
    otro = parse_envelope(body("kenko.auth", "PasswordResetTooManyRequests"))

    assert router.route(otro) is None


def test_dispatch_de_evento_desconocido_lanza_permanente():
    router = build_test_router()
    otro = parse_envelope(body("kenko.auth", "PasswordResetTooManyRequests"))

    with pytest.raises(UnsupportedEventError):
        router.dispatch(otro)


def test_source_ajeno_no_tiene_ruta(password_reset_event):
    """Mismo detail-type pero de otro productor: no debe escucharse."""
    password_reset_event["source"] = "kenko.profile"
    router = build_test_router()

    assert router.route(parse_envelope(json.dumps(password_reset_event))) is None
