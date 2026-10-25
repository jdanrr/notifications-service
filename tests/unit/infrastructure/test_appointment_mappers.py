"""Mappers de Appointments: sobre -> comando, con las fixtures reales."""

import pytest

from notifications.domain.errors import PermanentNotificationError
from notifications.infrastructure.inbound.sqs.envelope import parse_envelope
from notifications.infrastructure.inbound.sqs.mappers import (
    envelope_to_appointment_cancelled_command,
    envelope_to_appointment_rescheduled_command,
    envelope_to_appointment_scheduled_command,
)


def test_scheduled_mapea_todos_los_campos(appointment_scheduled_envelope):
    command = envelope_to_appointment_scheduled_command(appointment_scheduled_envelope)

    assert command.kind == "scheduled"
    assert command.event_id == "0192b3e0-5f11-7a22-9b33-4c5d6e7f8091"
    assert command.correlation_id == "7e8f9a0b-2c3d-4e5f-9a1b-3c4d5e6f7a8b"
    assert command.user_name == "Maria Fernanda"
    assert command.email == "maria.gomez@example.com"
    assert command.appointment_type == "ODONTOLOGIA"
    assert command.date == "2026-10-20"
    assert command.weekday == "Tuesday"
    assert command.start_time == "09:00"
    assert command.end_time == "09:30"
    assert command.physician_name == "Laura Gómez"
    assert command.medical_center_name == "Centro Médico Norte"
    assert command.medical_center_location == "Calle 100 # 15-20, Bogotá"


def test_rescheduled_trae_cita_anterior(appointment_rescheduled_envelope):
    command = envelope_to_appointment_rescheduled_command(appointment_rescheduled_envelope)

    assert command.kind == "rescheduled"
    assert command.date == "2026-10-25"
    assert command.start_time == "14:00"
    assert command.previous_date == "2026-10-20"
    assert command.previous_start_time == "09:00"


def test_cancelled_mapea_la_cita(appointment_cancelled_envelope):
    command = envelope_to_appointment_cancelled_command(appointment_cancelled_envelope)

    assert command.kind == "cancelled"
    assert command.appointment_type == "ODONTOLOGIA"
    assert command.date == "2026-10-20"
    assert command.previous_date is None


def test_detail_invalido_es_permanente(appointment_scheduled_envelope):
    detail = dict(appointment_scheduled_envelope.detail)
    detail["data"] = {"firstName": "Sin email ni cita"}
    envelope = appointment_scheduled_envelope.__class__(
        source=appointment_scheduled_envelope.source,
        detail_type=appointment_scheduled_envelope.detail_type,
        event_id=appointment_scheduled_envelope.event_id,
        correlation_id=appointment_scheduled_envelope.correlation_id,
        detail=detail,
    )

    with pytest.raises(PermanentNotificationError):
        envelope_to_appointment_scheduled_command(envelope)


def test_sobre_sin_metadata_falla_en_el_sobre():
    with pytest.raises(PermanentNotificationError):
        parse_envelope('{"source": "kenko.appointments", "detail-type": "X"}')
