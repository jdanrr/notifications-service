"""Modelos de aplicación: datos que viajan entre puertos y casos de uso."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WelcomeEmailData:
    """Campos mínimos del correo de bienvenida (los únicos que consumimos)."""

    user_name: str
    email: str


@dataclass(frozen=True)
class WelcomeBrandConfig:
    """Contexto de marca que el template exige y que no viene del evento."""

    app_name: str
    portal_url: str
    support_email: str
    logo_url: str
