"""Adaptador outbound: envio de correos con AWS SES (cliente v1 `ses`).

Mapeo de errores:
- Permanent -> no reintentar (destinatario no verificado, remitente rechazado).
- Transient -> reintentar (throttling, 5xx, red). Si SQS agota reintentos, DLQ.
"""

from botocore.exceptions import BotoCoreError, ClientError

from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)

# Errores de SES que no se arreglan reintentando.
PERMANENT_SES_ERRORS = frozenset(
    {
        "MessageRejected",
        "MailFromDomainNotVerified",
        "ConfigurationSetDoesNotExist",
        "AccountSendingDisabled",
        "FromAddressNotVerifiedException",
    }
)

# Fallos de red / servicio. Si aparece uno nuevo y no esta en PERMANENT, es
# transitorio (por defecto se reintenta, asi no se pierden correos).
TRANSIENT_SES_ERRORS = frozenset(
    {
        "Throttling",
        "ThrottlingException",
        "ServiceUnavailable",
        "ServiceUnavailableException",
        "InternalFailure",
        "InternalError",
        "RequestTimeout",
    }
)


class SesEmailSender:
    def __init__(self, client, sender: str) -> None:
        self._client = client
        self._sender = sender

    def send(self, *, subject: str, html: str, text: str, to: str) -> None:
        try:
            self._client.send_email(
                Source=self._sender,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html, "Charset": "UTF-8"},
                        "Text": {"Data": text, "Charset": "UTF-8"},
                    },
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in PERMANENT_SES_ERRORS:
                raise PermanentNotificationError(f"SES rechazo el correo: {code}") from exc
            raise TransientNotificationError(f"SES fallo (reintentable): {code}") from exc
        except BotoCoreError as exc:
            # Red, DNS, timeouts, credenciales: todo transitorio.
            raise TransientNotificationError(f"SES inalcanzable: {type(exc).__name__}") from exc
