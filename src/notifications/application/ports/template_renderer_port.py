"""Puerto: renderizado de plantillas. Implementado por el adaptador Jinja2."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class TemplateRendererPort(Protocol):
    def render(self, template_name: str, context: dict[str, object]) -> str:
        """Devuelve la plantilla ya renderizada con el contexto dado."""
        ...
