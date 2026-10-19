"""Validación del detail de PasswordResetRequested (Pydantic v2, solo infra)."""

import pytest
from pydantic import ValidationError

from notifications.infrastructure.inbound.sqs.schemas.auth import (
    PasswordResetRequestedDetail,
)

# expiresAt en el futuro: el valor de el ejemplo (2026-10-18T22:15Z) ya vencio.
BASE_DETAIL = {
    "metadata": {
        "eventId": "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e0f",
        "eventVersion": "1",
        "occurredAt": "2026-10-18T21:45:30.000Z",
        "correlationId": "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e10",
    },
    "data": {
        "userId": "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e11",
        "email": "maria.gomez@example.com",
        "firstName": "Maria Fernanda",
        "resetUrl": "http://localhost:8080/reset#token=EXAMPLE_TOKEN",
        "expiresAt": "2030-10-18T22:15:30.000Z",
    },
}


def detail(**overrides) -> dict:
    copia = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_DETAIL.items()}
    copia["data"] = {**copia["data"], **overrides.get("data", {})}
    if "metadata" in overrides:
        copia["metadata"] = overrides["metadata"]
    return copia


def test_evento_valido():
    parsed = PasswordResetRequestedDetail.model_validate(detail())

    assert parsed.metadata.event_id == "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e0f"
    assert parsed.metadata.correlation_id == "0192b3d1-1a2b-7c3d-8e4f-5a6b7c8d9e10"
    assert parsed.data.email == "maria.gomez@example.com"
    assert parsed.data.first_name == "Maria Fernanda"
    assert parsed.data.reset_url == "http://localhost:8080/reset#token=EXAMPLE_TOKEN"


def test_datetimes_con_zona():
    parsed = PasswordResetRequestedDetail.model_validate(detail())

    assert parsed.metadata.occurred_at.tzinfo is not None
    assert parsed.data.expires_at.tzinfo is not None


def test_acepta_https_y_localhost_en_dev():
    for url in ("https://kenko.example.com/reset#token=T", "http://localhost:8080/reset#token=T"):
        parsed = PasswordResetRequestedDetail.model_validate(detail(data={"resetUrl": url}))
        assert parsed.data.reset_url == url


def test_sin_email_es_invalido():
    d = detail()
    del d["data"]["email"]
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(d)


@pytest.mark.parametrize("email", ["no-es-email", "sin-arroba.com", "@sin-local.com"])
def test_email_invalido(email):
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(detail(data={"email": email}))


@pytest.mark.parametrize(
    "url", ["ftp://x.com/a", "javascript:alert(1)", "/ruta/relativa", "not a url"]
)
def test_reset_url_que_no_sea_http_s(url):
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(detail(data={"resetUrl": url}))


def test_sin_expires_at_es_invalido():
    d = detail()
    del d["data"]["expiresAt"]
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(d)


def test_expires_at_sin_zona_es_invalido():
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(
            detail(data={"expiresAt": "2030-10-18T22:15:30"})
        )


def test_campos_extra_no_rompen():
    d = detail()
    d["data"]["nuevoCampo"] = "que-agrega-auth"
    d["detail-version"] = "2"
    d["metadata"]["otro"] = "x"

    parsed = PasswordResetRequestedDetail.model_validate(d)
    assert parsed.data.email == "maria.gomez@example.com"


def test_first_name_se_repara_y_no_vacio():
    parsed = PasswordResetRequestedDetail.model_validate(
        detail(data={"firstName": "  Maria Fernanda  "})
    )
    assert parsed.data.first_name == "Maria Fernanda"

    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(detail(data={"firstName": "   "}))


def test_metadata_obligatoria():
    d = detail()
    del d["metadata"]["correlationId"]
    with pytest.raises(ValidationError):
        PasswordResetRequestedDetail.model_validate(d)
