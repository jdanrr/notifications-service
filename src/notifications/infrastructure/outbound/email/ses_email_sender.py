"""Adaptador outbound: envio de correos con AWS SES (cliente v1 `ses`).

El logo va EMBEBIDO en el correo (Content-ID `cid:logo`), no por URL: la
URL anterior apuntaba a un dominio de ejemplo que no resuelve y ningun
cliente mostraba la imagen. Se usa `send_raw_email` con MIME
`multipart/related` (alternativa texto+html y la imagen inline).

Mapeo de errores:
- Permanent -> no reintentar (destinatario no verificado, remitente rechazado).
- Transient -> reintentar (throttling, 5xx, red). Si SQS agota reintentos, DLQ.
"""

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from botocore.exceptions import BotoCoreError, ClientError

from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)

# Content-ID que referencia el template base (`<img src="cid:logo">`).
LOGO_CONTENT_ID = "logo"

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
    def __init__(self, client, sender: str, logo: bytes) -> None:
        self._client = client
        self._sender = sender
        self._logo = logo

    def send(self, *, subject: str, html: str, text: str, to: str) -> None:
        raw = self._build_raw_message(subject=subject, html=html, text=text, to=to)
        try:
            self._client.send_raw_email(
                Source=self._sender,
                Destinations=[to],
                RawMessage={"Data": raw},
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in PERMANENT_SES_ERRORS:
                raise PermanentNotificationError(f"SES rechazo el correo: {code}") from exc
            raise TransientNotificationError(f"SES fallo (reintentable): {code}") from exc
        except BotoCoreError as exc:
            # Red, DNS, timeouts, credenciales: todo transitorio.
            raise TransientNotificationError(f"SES inalcanzable: {type(exc).__name__}") from exc

    def _build_raw_message(self, *, subject: str, html: str, text: str, to: str) -> str:
        message = MIMEMultipart("related")
        message["Subject"] = subject
        message["From"] = self._sender
        message["To"] = to

        alternative = MIMEMultipart("alternative")
        message.attach(alternative)
        alternative.attach(MIMEText(text, "plain", "utf-8"))
        alternative.attach(MIMEText(html, "html", "utf-8"))

        image = MIMEImage(self._logo, "png")
        image.add_header("Content-ID", f"<{LOGO_CONTENT_ID}>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        message.attach(image)

        return message.as_string()
