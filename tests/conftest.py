"""Fixtures compartidas de los tests de Notifications."""

import json
from pathlib import Path

import pytest

from notifications.application.models import WelcomeBrandConfig
from notifications.infrastructure.inbound.sqs.envelope import parse_envelope
from notifications.infrastructure.outbound.rendering.jinja_renderer import (
    JinjaTemplateRenderer,
)
from tests.fakes.fake_email_sender import FakeEmailSender
from tests.fakes.in_memory_notification_log_repository import (
    InMemoryNotificationLogRepository,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "events"


@pytest.fixture
def welcome_event_json() -> str:
    return (FIXTURES_DIR / "user_registered.json").read_text(encoding="utf-8")


@pytest.fixture
def welcome_event(welcome_event_json) -> dict:
    return json.loads(welcome_event_json)


@pytest.fixture
def welcome_envelope(welcome_event_json):
    return parse_envelope(welcome_event_json)


@pytest.fixture
def password_reset_event_json() -> str:
    return (FIXTURES_DIR / "password_reset_requested.json").read_text(encoding="utf-8")


@pytest.fixture
def password_reset_event(password_reset_event_json) -> dict:
    return json.loads(password_reset_event_json)


@pytest.fixture
def password_reset_envelope(password_reset_event_json):
    return parse_envelope(password_reset_event_json)


@pytest.fixture
def appointment_scheduled_envelope():
    return parse_envelope((FIXTURES_DIR / "appointment_scheduled.json").read_text(encoding="utf-8"))


@pytest.fixture
def appointment_rescheduled_envelope():
    return parse_envelope(
        (FIXTURES_DIR / "appointment_rescheduled.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def appointment_cancelled_envelope():
    return parse_envelope((FIXTURES_DIR / "appointment_cancelled.json").read_text(encoding="utf-8"))


@pytest.fixture
def brand() -> WelcomeBrandConfig:
    return WelcomeBrandConfig(
        app_name="Kenko",
        portal_url="https://kenko.example.com",
        support_email="soporte@kenko.example.com",
        logo_url="https://cdn.kenko.example.com/img/kenko_limpio.png",
    )


@pytest.fixture
def renderer() -> JinjaTemplateRenderer:
    return JinjaTemplateRenderer()


@pytest.fixture
def fake_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def fake_repository() -> InMemoryNotificationLogRepository:
    return InMemoryNotificationLogRepository()
