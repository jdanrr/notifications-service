"""Tests del render Jinja2: variables esperadas y autoescape activado."""

import pytest

from notifications.domain.errors import PermanentNotificationError

CONTEXT = {
    "user_name": "Maria Fernanda",
    "email": "maria.gomez@example.com",
    "app_name": "Kenko",
    "portal_url": "https://kenko.example.com",
    "support_email": "soporte@kenko.example.com",
    "logo_url": "https://cdn.kenko.example.com/img/kenko_limpio.png",
    "current_year": 2026,
}


def test_render_html_con_todas_las_variables(renderer):
    html = renderer.render("auth/welcome.html.j2", CONTEXT)

    assert "<!doctype html>" in html
    assert "Maria Fernanda" in html
    assert "maria.gomez@example.com" in html
    assert "https://kenko.example.com" in html
    assert "soporte@kenko.example.com" in html
    assert "cid:logo" in html
    assert "2026" in html


def test_render_text_es_alternativa_plana(renderer):
    text = renderer.render("auth/welcome.txt.j2", CONTEXT)

    assert "Maria Fernanda" in text
    assert "Ingresar al portal: https://kenko.example.com" in text
    assert "<" not in text  # sin marcado HTML


def test_autoescape_en_html_protege_contra_xss(renderer):
    context = dict(CONTEXT, user_name="<script>alert('xss')</script>")

    html = renderer.render("auth/welcome.html.j2", context)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_texto_plano_no_escapa(renderer):
    context = dict(CONTEXT, user_name="<b>Hola</b>")

    text = renderer.render("auth/welcome.txt.j2", context)

    assert "<b>Hola</b>" in text


def test_variable_faltante_es_error_permanente(renderer):
    incomplete = {k: v for k, v in CONTEXT.items() if k != "support_email"}

    with pytest.raises(PermanentNotificationError):
        renderer.render("auth/welcome.html.j2", incomplete)


def test_plantilla_inexistente_es_permanente(renderer):
    with pytest.raises(PermanentNotificationError):
        renderer.render("auth/no_existe.html.j2", CONTEXT)
