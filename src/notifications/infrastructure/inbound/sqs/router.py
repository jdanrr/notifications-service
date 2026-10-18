"""Router: (source, detail-type) -> ruta (handler + metadatos del evento).

Para agregar un evento nuevo se registra una entrada en el contenedor; este
archivo no cambia.

`template_name` vive AQUI y no en el worker: cada evento reporta su propia
plantilla cuando hay que registrar un fallo. Si viviera en el worker, todos
los fallos de la cola quedarian con la misma plantilla y la traza mintiria.
"""

from collections.abc import Callable
from dataclasses import dataclass

from notifications.infrastructure.inbound.sqs.envelope import Envelope

Handler = Callable[[Envelope], str]


@dataclass(frozen=True)
class Route:
    handler: Handler
    template_name: str


class EventRouter:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Route] = {}

    def register(
        self,
        source: str,
        detail_type: str,
        handler: Handler,
        *,
        template_name: str,
    ) -> None:
        self._routes[(source, detail_type)] = Route(handler=handler, template_name=template_name)

    def route(self, envelope: Envelope) -> Route | None:
        """Devuelve la ruta del evento, o None si nadie lo escucha."""
        return self._routes.get((envelope.source, envelope.detail_type))
