"""Sincronizacion entre Terraform y el router de la aplicacion.

Terraform decide QUE eventos llegan a cada cola (`auth_detail_types` y
`appointments_detail_types`) y el container decide QUE eventos sabemos
procesar (build_router). Son dos lados del mismo contrato y pueden
desincronizarse en silencio:

- En tfvars sin handler  -> el worker recibe el evento, no encuentra ruta,
  lo registra como failed/unknown y lo borra. Se descarta con traza, pero no
  se envia ningun correo.
- Handler sin tfvars     -> codigo muerto: nadie envia ese evento a la cola.

Ambos casos fallan aqui. La comparacion es por productor (source), porque
cada cola agrupa los eventos de un solo productor.
"""

import re
from pathlib import Path

import pytest

from notifications.application.models import WelcomeBrandConfig
from notifications.application.use_cases.appointments.send_appointment_cancelled_email import (
    SendAppointmentCancelledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_rescheduled_email import (
    SendAppointmentRescheduledEmailUseCase,
)
from notifications.application.use_cases.appointments.send_appointment_scheduled_email import (
    SendAppointmentScheduledEmailUseCase,
)
from notifications.application.use_cases.auth.send_password_reset_email import (
    SendPasswordResetEmailUseCase,
)
from notifications.application.use_cases.auth.send_welcome_email import (
    SendWelcomeEmailUseCase,
)
from notifications.infrastructure.container import (
    APPOINTMENTS_SOURCE,
    AUTH_SOURCE,
    build_router,
)
from notifications.infrastructure.outbound.rendering.jinja_renderer import (
    JinjaTemplateRenderer,
)
from tests.fakes.fake_email_sender import FakeEmailSender
from tests.fakes.in_memory_notification_log_repository import (
    InMemoryNotificationLogRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TFVARS_DIR = REPO_ROOT / "terraform" / "envs"

# Variable del .tfvars por cada source que escucha el router.
TFVARS_BY_SOURCE = {
    AUTH_SOURCE: "auth_detail_types",
    APPOINTMENTS_SOURCE: "appointments_detail_types",
}


def detail_types_from_tfvars(path: Path, variable: str) -> list[str]:
    """Extrae una lista de un .tfvars sin depender de un parser HCL."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{variable}\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def build_test_router():
    """Router real, con adaptadores falsos (sin AWS)."""
    renderer = JinjaTemplateRenderer()
    repository = InMemoryNotificationLogRepository()
    brand = WelcomeBrandConfig(
        app_name="Kenko",
        portal_url="https://kenko.example.com",
        support_email="soporte@kenko.example.com",
        logo_url="https://cdn.kenko.example.com/img/kenko_limpio.png",
    )
    common = dict(renderer=renderer, sender=FakeEmailSender(), repository=repository, brand=brand)
    return build_router(
        SendWelcomeEmailUseCase(**common),
        SendPasswordResetEmailUseCase(**common),
        SendAppointmentScheduledEmailUseCase(**common),
        SendAppointmentRescheduledEmailUseCase(**common),
        SendAppointmentCancelledEmailUseCase(**common),
    )


def registered_by_source() -> dict[str, set[str]]:
    """Detail-types que la aplicacion sabe procesar, agrupados por source."""
    grouped: dict[str, set[str]] = {}
    for source, detail_type in build_test_router().registered_routes():
        grouped.setdefault(source, set()).add(detail_type)
    return grouped


def tfvars_files() -> list[Path]:
    files = sorted(TFVARS_DIR.glob("*.tfvars"))
    assert files, f"no se encontraron .tfvars en {TFVARS_DIR}"
    return files


@pytest.mark.parametrize("tfvars", tfvars_files(), ids=lambda p: p.stem)
@pytest.mark.parametrize("source,variable", list(TFVARS_BY_SOURCE.items()))
def test_eventos_en_tfvars_tienen_handler(tfvars: Path, source: str, variable: str):
    """Todo evento que Terraform enruta debe tener caso de uso registrado."""
    declared = detail_types_from_tfvars(tfvars, variable)
    assert declared, f"{tfvars.name} no declara {variable}"

    handled = registered_by_source().get(source, set())
    missing = set(declared) - handled
    assert not missing, (
        f"{tfvars.name} enruta {sorted(missing)} de {source} pero build_router() "
        f"no tiene handler: el worker los descartaria como unknown. "
        f"Registrados: {sorted(handled)}"
    )


@pytest.mark.parametrize("tfvars", tfvars_files(), ids=lambda p: p.stem)
@pytest.mark.parametrize("source,variable", list(TFVARS_BY_SOURCE.items()))
def test_handlers_estan_en_tfvars(tfvars: Path, source: str, variable: str):
    """Todo handler registrado debe venir enrutado por Terraform."""
    declared = set(detail_types_from_tfvars(tfvars, variable))
    handled = registered_by_source().get(source, set())

    orphan = handled - declared
    assert not orphan, (
        f"{tfvars.name} no enruta {sorted(orphan)} de {source} aunque "
        f"build_router() lo registra: ese codigo nunca se ejecutaria. "
        f"En tfvars: {sorted(declared)}"
    )


def _source_variable_from_terraform(variable: str) -> str:
    variables_tf = (REPO_ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    match = re.search(
        rf'variable\s+"{variable}"[^}}]*?default\s*=\s*"([^"]+)"', variables_tf, re.DOTALL
    )
    assert match, f"no se encontro variable {variable} en terraform/variables.tf"
    return match.group(1)


def test_fuentes_coinciden_con_terraform():
    """Los sources del router deben ser los mismos que declara variables.tf."""
    expected = {
        _source_variable_from_terraform("auth_source"),
        _source_variable_from_terraform("appointments_source"),
    }
    registered = set(registered_by_source())

    assert registered == expected, (
        f"router escucha {sorted(registered)} pero Terraform usa {sorted(expected)}"
    )
