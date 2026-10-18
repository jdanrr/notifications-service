"""Tests de dominio: jerarquia de errores (permanente vs transitorio)."""

from notifications.domain.errors import (
    DuplicateEventError,
    NotificationError,
    PermanentNotificationError,
    TransientNotificationError,
    UnsupportedEventError,
)


def test_permanente_y_transitorio_son_de_dominio():
    assert issubclass(PermanentNotificationError, NotificationError)
    assert issubclass(TransientNotificationError, NotificationError)
    assert issubclass(DuplicateEventError, NotificationError)


def test_permanente_y_transitorio_no_se_confunden():
    assert not issubclass(PermanentNotificationError, TransientNotificationError)
    assert not issubclass(TransientNotificationError, PermanentNotificationError)


def test_evento_sin_handler_es_permanente():
    assert issubclass(UnsupportedEventError, PermanentNotificationError)
