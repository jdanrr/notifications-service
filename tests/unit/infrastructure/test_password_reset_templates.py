"""Render de las plantillas de restablecimiento (HTML con autoescape y texto)."""

import pytest

from notifications.domain.errors import PermanentNotificationError

RESET_URL = "http://localhost:8080/reset#token=EXAMPLE_TOKEN"

CONTEXT = {
    "first_name": "Maria Fernanda",
    "reset_url": RESET_URL,
    "expires_at": "18/10/2030 17:15",
    "app_name": "Kenko",
    "portal_url": "https://kenko.example.com",
    "support_email": "soporte@kenko.example.com",
    "logo_url": "https://cdn.kenko.example.com/img/kenko_limpio.png",
    "current_year": 2026,
}


def test_html_contiene_url_nombre_y_fecha(renderer):
    html = renderer.render("auth/password_reset.html.j2", CONTEXT)

    assert RESET_URL in html
    assert "Maria Fernanda" in html
    assert "18/10/2030 17:15" in html
    assert "Restablecer contraseña" in html
    assert "solo se puede usar una vez" in html
    assert "nunca te pedirá tu contraseña" in html


def test_texto_contiene_url_nombre_y_fecha(renderer):
    text = renderer.render("auth/password_reset.txt.j2", CONTEXT)

    assert RESET_URL in text
    assert "Maria Fernanda" in text
    assert "18/10/2030 17:15" in text
    assert "solo se puede usar una vez" in text


def test_html_es_alternativa_html_y_texto_plano(renderer):
    html = renderer.render("auth/password_reset.html.j2", CONTEXT)
    text = renderer.render("auth/password_reset.txt.j2", CONTEXT)

    assert "<" in html and "<html" in html
    assert "<html" not in text  # la version txt no lleva marcado


def test_autoescape_en_html_no_en_texto(renderer):
    ctx = dict(CONTEXT, first_name="<script>alert(1)</script>")

    html = renderer.render("auth/password_reset.html.j2", ctx)
    text = renderer.render("auth/password_reset.txt.j2", ctx)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in text


@pytest.mark.parametrize("missing", ["first_name", "reset_url", "expires_at"])
def test_variable_faltante_da_error_no_correo_con_huecos(renderer, missing):
    ctx = {k: v for k, v in CONTEXT.items() if k != missing}

    with pytest.raises(PermanentNotificationError):
        renderer.render("auth/password_reset.html.j2", ctx)
    with pytest.raises(PermanentNotificationError):
        renderer.render("auth/password_reset.txt.j2", ctx)
