"""Adaptador inbound: lectura y borrado de mensajes en SQS.

Long polling con WaitTimeSeconds. El visibility timeout NO se sobreescribe:
se usa el que define Terraform en la cola (60 s).
"""

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


class SqsPoller:
    def __init__(self, client, queue_url: str, batch_size: int = 1, wait_time_seconds: int = 20):
        self._client = client
        self._queue_url = queue_url
        self._batch_size = batch_size
        self._wait_time_seconds = wait_time_seconds

    def receive(self) -> list[SqsMessage]:
        """Bloquea hasta WaitTimeSeconds si no hay mensajes. Devuelve [] si no llega nada."""
        try:
            response = self._client.receive_message(
                QueueUrl=self._queue_url,
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
            SqsMessage(receipt_handle=m["ReceiptHandle"], body=m["Body"])
            for m in response.get("Messages", [])
        ]

    def delete(self, receipt_handle: str) -> None:
        """Borra el mensaje. Solo se llama tras exito o fallo permanente registrado."""
        self._client.delete_message(
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
        )


def _is_permanent(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in PERMANENT_SQS_ERRORS
    return False
