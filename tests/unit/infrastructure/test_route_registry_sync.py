"""Sincronizacion entre Terraform y el router de la aplicacion.

Terraform decide QUE eventos llegan a la cola (auth_detail_types) y el
container decide QUE eventos sabemos procesar (build_router). Son dos lados
del mismo contrato y pueden desincronizarse en silencio:

- En tfvars sin handler  -> el worker recibe el evento, no encuentra ruta,
  lo registra como failed/unknown y lo borra. Se descarta con traza, pero no
  se envia ningun correo.
- Handler sin tfvars     -> codigo muerto: nadie envia ese evento a la cola.

Ambos casos fallan aqui.
"""

import re
from pathlib import Path

import pytest

from notifications.application.models import WelcomeBrandConfig
from notifications.application.use_cases.auth.send_password_reset_email import (
    SendPasswordResetEmailUseCase,
)
from notifications.application.use_cases.auth.send_welcome_email import (
    SendWelcomeEmailUseCase,
)
from notifications.infrastructure.container import build_router
from notifications.infrastructure.outbound.rendering.jinja_renderer import (
    JinjaTemplateRenderer,
)
from tests.fakes.fake_email_sender import FakeEmailSender
from tests.fakes.in_memory_notification_log_repository import (
    InMemoryNotificationLogRepository,
)

SOURCE = "kenko.auth"
REPO_ROOT = Path(__file__).resolve().parents[3]
TFVARS_DIR = REPO_ROOT / "terraform" / "envs"


def detail_types_from_tfvars(path: Path) -> list[str]:
    """Extrae auth_detail_types de un .tfvars sin depender de un parser HCL."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^\s*auth_detail_types\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
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
    )


def registered_detail_types() -> set[str]:
    """Detail-types que la aplicacion sabe procesar."""
    return {detail_type for _, detail_type in build_test_router().registered_routes()}


def tfvars_files() -> list[Path]:
    files = sorted(TFVARS_DIR.glob("*.tfvars"))
    assert files, f"no se encontraron .tfvars en {TFVARS_DIR}"
    return files


@pytest.mark.parametrize("tfvars", tfvars_files(), ids=lambda p: p.stem)
def test_eventos_en_tfvars_tienen_handler(tfvars: Path):
    """Todo evento que Terraform enruta debe tener caso de uso registrado."""
    declared = detail_types_from_tfvars(tfvars)
    assert declared, f"{tfvars.name} no declara auth_detail_types"

    handled = registered_detail_types()
    missing = set(declared) - handled
    assert not missing, (
        f"{tfvars.name} enruta {sorted(missing)} pero build_router() no tiene "
        f"handler: el worker los descartaria como unknown. "
        f"Registrados: {sorted(handled)}"
    )


@pytest.mark.parametrize("tfvars", tfvars_files(), ids=lambda p: p.stem)
def test_handlers_estan_en_tfvars(tfvars: Path):
    """Todo handler registrado debe venir enrutado por Terraform."""
    declared = set(detail_types_from_tfvars(tfvars))
    handled = registered_detail_types()

    orphan = handled - declared
    assert not orphan, (
        f"{tfvars.name} no enruta {sorted(orphan)} aunque build_router() lo "
        f"registra: ese codigo nunca se ejecutaria. "
        f"En tfvars: {sorted(declared)}"
    )


def test_fuente_coincide_con_terraform():
    """El source del router debe ser el mismo que declara variables.tf."""
    variables_tf = (REPO_ROOT / "terraform" / "variables.tf").read_text(encoding="utf-8")
    match = re.search(
        r'variable\s+"auth_source"[^}]*?default\s*=\s*"([^"]+)"', variables_tf, re.DOTALL
    )
    assert match, "no se encontro variable auth_source en terraform/variables.tf"

    registered = {source for source, _ in build_test_router().registered_routes()}

    assert registered == {match.group(1)}, (
        f"router escucha {sorted(registered)} pero Terraform usa {match.group(1)}"
    )
