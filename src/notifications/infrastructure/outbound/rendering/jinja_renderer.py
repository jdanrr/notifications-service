"""Adaptador outbound: render de plantillas con Jinja2.

- autoescape ACTIVADO para .html.j2 (el nombre de usuario viene del usuario
  y puede contener HTML/marcas).
- autoescape DESACTIVADO para .txt.j2 (texto plano: no se escapa).
- StrictUndefined: si falta una variable de config, falla en seco en vez de
  generar un correo con huecos vacios.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from notifications.domain.errors import PermanentNotificationError

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
HTML_SUFFIX = ".html.j2"


class JinjaTemplateRenderer:
    def __init__(self, templates_dir: Path | None = None) -> None:
        directory = templates_dir or TEMPLATES_DIR
        loader = FileSystemLoader(str(directory))
        self._html_env = Environment(
            loader=loader,
            autoescape=True,
            undefined=StrictUndefined,
        )
        self._text_env = Environment(
            loader=loader,
            autoescape=False,
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, context: dict[str, object]) -> str:
        env = self._html_env if template_name.endswith(HTML_SUFFIX) else self._text_env
        try:
            return env.get_template(template_name).render(**context)
        except TemplateError as exc:
            # Plantilla mal configurada: reintentar no la arregla.
            raise PermanentNotificationError(
                f"no se pudo renderizar {template_name}: {type(exc).__name__}"
            ) from exc
