"""Router: (source, detail-type) -> caso de uso.

Para agregar un evento nuevo se registra una entrada en el contenedor; este
archivo no cambia.
"""

from collections.abc import Callable

from notifications.domain.errors import UnsupportedEventError
from notifications.infrastructure.inbound.sqs.envelope import Envelope

Handler = Callable[[Envelope], str]


class EventRouter:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Handler] = {}

    def register(self, source: str, detail_type: str, handler: Handler) -> None:
        self._routes[(source, detail_type)] = handler

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
        handler = self._routes.get((envelope.source, envelope.detail_type))
        if handler is None:
            raise UnsupportedEventError(
                f"sin handler para {envelope.source}/{envelope.detail_type}"
            )
        return handler(envelope)
