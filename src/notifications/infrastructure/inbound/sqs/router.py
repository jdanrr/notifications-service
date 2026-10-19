"""Router: (source, detail-type) -> ruta (handler + plantilla del evento).

Para agregar un evento nuevo se registra una entrada en `container.build_router`;
este archivo no cambia.

`template_name` vive AQUI y no en el worker: cada evento reporta su propia
plantilla al registrar un fallo. Si viviera en el worker, todos los fallos de
la cola quedarian con la misma plantilla y la traza mintiria.
"""

from collections.abc import Callable
from dataclasses import dataclass

from notifications.domain.errors import UnsupportedEventError
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
        """Ruta del evento, o None si nadie lo escucha."""
        return self._routes.get((envelope.source, envelope.detail_type))

    def registered_routes(self) -> set[tuple[str, str]]:
        """Claves (source, detail_type) que este router escucha.

        La usa el test que compara contra `auth_detail_types` de Terraform,
        para que ninguno de los dos lados se desincronice en silencio.
        """
        return set(self._routes)

    def dispatch(self, envelope: Envelope) -> str:
        """Ejecuta el caso de uso correspondiente y devuelve el resultado.

        Lanza UnsupportedEventError si nadie escucha ese evento.
        """
        route = self.route(envelope)
        if route is None:
            raise UnsupportedEventError(
                f"sin handler para {envelope.source}/{envelope.detail_type}"
            )
        return route.handler(envelope)
