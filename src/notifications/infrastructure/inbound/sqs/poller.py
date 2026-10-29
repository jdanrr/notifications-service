"""Adaptador inbound: lectura y borrado de mensajes en SQS.

Lee varias colas con un solo proceso, rotando entre ellas (round-robin):
cada llamada a `receive()` consulta la siguiente cola. Con long polling
el peor caso agrega ~WaitTimeSeconds de latencia a una cola mientras la
otra esta vacia.

Long polling con WaitTimeSeconds. El visibility timeout NO se sobreescribe:
se usa el que define Terraform en cada cola (60 s).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from botocore.exceptions import BotoCoreError, ClientError

PERMANENT_SQS_ERRORS = frozenset(
    {
        "ReceiptHandleIsInvalid",
        "InvalidAddress",
        "InvalidSecurity",
    }
)


@dataclass(frozen=True)
class SqsMessage:
    receipt_handle: str
    body: str
    # Cola de origen: el borrado debe ir a la misma cola que entrego.
    queue_url: str


class SqsPoller:
    def __init__(
        self,
        client,
        queue_urls: Sequence[str],
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ):
        urls = list(queue_urls)
        if not urls:
            raise ValueError("se requiere al menos una cola SQS")
        self._client = client
        self._queue_urls = urls
        self._batch_size = batch_size
        self._wait_time_seconds = wait_time_seconds
        self._next = 0

    @property
    def queue_urls(self) -> list[str]:
        return list(self._queue_urls)

    def receive(self) -> list[SqsMessage]:
        """Lee la siguiente cola (round-robin). Bloquea hasta
        WaitTimeSeconds si no hay mensajes. Devuelve [] si no llega nada."""
        queue_url = self._queue_urls[self._next]
        self._next = (self._next + 1) % len(self._queue_urls)
        try:
            response = self._client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=self._batch_size,
                WaitTimeSeconds=self._wait_time_seconds,
                MessageSystemAttributeNames=["ApproximateReceiveCount"],
            )
        except (ClientError, BotoCoreError) as exc:
            if _is_permanent(exc):
                # Cola inexistente o credenciales invalidas: reintentar no ayuda.
                raise
            raise

        return [
            SqsMessage(receipt_handle=m["ReceiptHandle"], body=m["Body"], queue_url=queue_url)
            for m in response.get("Messages", [])
        ]

    def delete(self, message: SqsMessage) -> None:
        """Borra el mensaje en su cola de origen. Solo se llama tras exito
        o fallo permanente registrado."""
        self._client.delete_message(
            QueueUrl=message.queue_url,
            ReceiptHandle=message.receipt_handle,
        )


def _is_permanent(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in PERMANENT_SQS_ERRORS
    return False
