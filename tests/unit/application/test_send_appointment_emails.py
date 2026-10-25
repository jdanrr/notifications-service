"""Casos de uso de Appointments con puertos falsos (sin AWS)."""

import pytest

from notifications.application.commands import AppointmentEmailCommand
from notifications.application.use_cases.appointments.send_appointment_cancelled_email import (
    SendAppointmentCancelledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_rescheduled_email import (
    SendAppointmentRescheduledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_scheduled_email import (
    SendAppointmentScheduledEmailUseCase,
)
from notifications.domain.errors import PermanentNotificationError


def _command(**overrides) -> AppointmentEmailCommand:
    base = dict(
        event_id="evt-1",
        correlation_id="corr-1",
        kind="scheduled",
        user_name="Maria Fernanda",
        email="maria.gomez@example.com",
        appointment_type="ODONTOLOGIA",
        date="2026-10-20",
        start_time="09:00",
        weekday="Tuesday",
        end_time="09:30",
        physician_name="Laura Gómez",
        medical_center_name="Centro Médico Norte",
        medical_center_location="Calle 100 # 15-20, Bogotá",
        previous_date="2026-10-18",
        previous_start_time="10:00",
    )
    base.update(overrides)
    return AppointmentEmailCommand(**base)


@pytest.fixture
def scheduled_use_case(renderer, fake_sender, fake_repository, brand):
    return SendAppointmentScheduledEmailUseCase(
        renderer=renderer, sender=fake_sender, repository=fake_repository, brand=brand
    )


@pytest.fixture
def rescheduled_use_case(renderer, fake_sender, fake_repository, brand):
    return SendAppointmentRescheduledEmailUseCase(
        renderer=renderer, sender=fake_sender, repository=fake_repository, brand=brand
    )


@pytest.fixture
def cancelled_use_case(renderer, fake_sender, fake_repository, brand):
    return SendAppointmentCancelledEmailUseCase(
        renderer=renderer, sender=fake_sender, repository=fake_repository, brand=brand
    )


def test_scheduled_envia_con_asunto_y_datos(scheduled_use_case, fake_sender):
    assert scheduled_use_case.execute(_command()) == "sent"

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu cita de ODONTOLOGIA quedó agendada"
    assert sent.to == "maria.gomez@example.com"
    assert "Maria Fernanda" in sent.html
    assert "2026-10-20" in sent.text
    assert "Laura Gómez" in sent.html
    assert "Centro Médico Norte" in sent.text


def test_rescheduled_muestra_fecha_anterior(rescheduled_use_case, fake_sender):
    rescheduled_use_case.execute(_command(kind="rescheduled"))

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu cita de ODONTOLOGIA fue reprogramada"
    assert "2026-10-18" in sent.html
    assert "2026-10-20" in sent.text


def test_cancelled_envia_con_asunto(cancelled_use_case, fake_sender):
    assert cancelled_use_case.execute(_command(kind="cancelled")) == "sent"

    sent = fake_sender.sent[0]
    assert sent.subject == "Tu cita de ODONTOLOGIA fue cancelada"
    assert "2026-10-20" in sent.html


def test_duplicado_no_reenvia(scheduled_use_case, fake_sender):
    assert scheduled_use_case.execute(_command()) == "sent"
    assert scheduled_use_case.execute(_command()) == "duplicate"
    assert len(fake_sender.sent) == 1


def test_sin_email_es_permanente(scheduled_use_case):
    with pytest.raises(PermanentNotificationError):
        scheduled_use_case.execute(_command(email="  "))


def test_registra_sent_con_plantilla(scheduled_use_case, fake_repository):
    scheduled_use_case.execute(_command())

    record = fake_repository.records[0]
    assert record.template == "appointment_scheduled"
    assert record.status == "sent"
