"""Render de las plantillas de Appointments (HTML con autoescape y texto)."""

import pytest

from notifications.domain.errors import PermanentNotificationError

CONTEXT = {
    "user_name": "Maria Fernanda",
    "appointment_type": "ODONTOLOGIA",
    "date": "2026-10-20",
    "weekday": "Tuesday",
    "start_time": "09:00",
    "end_time": "09:30",
    "physician_name": "Laura Gómez",
    "medical_center_name": "Centro Médico Norte",
    "medical_center_location": "Calle 100 # 15-20, Bogotá",
    "previous_date": "2026-10-18",
    "previous_start_time": "10:00",
    "app_name": "Kenko",
    "portal_url": "https://kenko.example.com",
    "support_email": "soporte@kenko.example.com",
    "logo_url": "https://cdn.kenko.example.com/img/kenko_limpio.png",
    "current_year": 2026,
}

TEMPLATES = [
    ("appointments/scheduled.html.j2", "appointments/scheduled.txt.j2"),
    ("appointments/rescheduled.html.j2", "appointments/rescheduled.txt.j2"),
    ("appointments/cancelled.html.j2", "appointments/cancelled.txt.j2"),
]


@pytest.mark.parametrize(("html_tpl", "txt_tpl"), TEMPLATES)
def test_contienen_datos_de_la_cita(renderer, html_tpl, txt_tpl):
    html = renderer.render(html_tpl, CONTEXT)
    text = renderer.render(txt_tpl, CONTEXT)

    for expected in ("Maria Fernanda", "ODONTOLOGIA", "2026-10-20", "Centro Médico Norte"):
        assert expected in html
        assert expected in text


def test_html_es_alternativa_html_y_texto_plano(renderer):
    html = renderer.render("appointments/scheduled.html.j2", CONTEXT)
    text = renderer.render("appointments/scheduled.txt.j2", CONTEXT)

    assert "<html" in html
    assert "<html" not in text


def test_autoescape_en_html_no_en_texto(renderer):
    ctx = dict(CONTEXT, physician_name="<script>alert(1)</script>")

    html = renderer.render("appointments/scheduled.html.j2", ctx)
    text = renderer.render("appointments/scheduled.txt.j2", ctx)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in text


@pytest.mark.parametrize("missing", ["user_name", "appointment_type", "date", "start_time"])
def test_variable_requerida_faltante_da_error(renderer, missing):
    ctx = {k: v for k, v in CONTEXT.items() if k != missing}

    with pytest.raises(PermanentNotificationError):
        renderer.render("appointments/scheduled.html.j2", ctx)


def test_opcionales_ausentes_no_fallan(renderer):
    ctx = {k: v for k, v in CONTEXT.items() if k not in ("physician_name", "weekday")}

    html = renderer.render("appointments/scheduled.html.j2", ctx)
    assert "Por asignar" in html
