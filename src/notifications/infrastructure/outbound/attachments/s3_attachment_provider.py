"""Adaptador outbound: descarga de adjuntos desde S3.

Mapeo de errores:
- Permanente -> la referencia está mal o el objeto no existe: reintentar
  entrega el mismo fallo (el mensaje se registra y se borra).
- Transitorio -> red, throttling o 5xx de S3: el mensaje NO se borra y SQS
  lo reentrega (luego DLQ si se agotan los reintentos).
"""

import logging

from botocore.exceptions import BotoCoreError, ClientError

from notifications.application.ports.email_sender_port import EmailAttachment
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)

logger = logging.getLogger(__name__)

# El objeto no está o la referencia es inválida: no se arregla reintentando.
PERMANENT_S3_ERRORS = frozenset(
    {
        "NoSuchKey",
        "NoSuchBucket",
        "InvalidObjectState",
        "InvalidArgument",
    }
)


class S3AttachmentProvider:
    def __init__(self, client) -> None:
        self._client = client

    def fetch(self, *, bucket: str, key: str) -> EmailAttachment:
        if not (bucket or "").strip() or not (key or "").strip():
            raise PermanentNotificationError("referencia S3 sin bucket o key")

        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in PERMANENT_S3_ERRORS:
                raise PermanentNotificationError(f"S3 no tiene el objeto: {code}") from exc
            raise TransientNotificationError(f"S3 fallo (reintentable): {code}") from exc
        except BotoCoreError as exc:
            # Red, DNS, timeouts, credenciales: todo transitorio.
            raise TransientNotificationError(f"S3 inalcanzable: {type(exc).__name__}") from exc

        if not content:
            raise PermanentNotificationError("S3 devolvio un objeto vacio")

        content_type = self._content_type(response) or "application/pdf"
        filename = key.rsplit("/", 1)[-1] or key
        logger.info("adjunto descargado de S3 bucket=%s key=%s bytes=%d", bucket, key, len(content))
        return EmailAttachment(filename=filename, content=content, content_type=content_type)

    @staticmethod
    def _content_type(response) -> str | None:
        value = response.get("ContentType")
        return value if isinstance(value, str) and value.strip() else None
