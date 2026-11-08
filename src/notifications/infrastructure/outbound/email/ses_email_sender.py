"""Adaptador outbound: envio de correos con AWS SES (cliente v1 `ses`).

El logo va EMBEBIDO en el correo (Content-ID `cid:logo`), no por URL: la
URL anterior apuntaba a un dominio de ejemplo que no resuelve y ningun
cliente mostraba la imagen. Se usa `send_raw_email` con MIME
`multipart/related` (alternativa texto+html y la imagen inline).

Con adjuntos (PDFs de Documents) el mensaje pasa a `multipart/mixed`:
la parte `related` anterior más un `application/*` por adjunto.

Mapeo de errores:
- Permanent -> no reintentar (destinatario no verificado, remitente rechazado).
- Transient -> reintentar (throttling, 5xx, red). Si SQS agota reintentos, DLQ.
"""

from collections.abc import Sequence
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from botocore.exceptions import BotoCoreError, ClientError

from notifications.application.ports.email_sender_port import EmailAttachment
from notifications.domain.errors import (
    PermanentNotificationError,
    TransientNotificationError,
)

# Content-ID que referencia el template base (`<img src="cid:logo">`).
LOGO_CONTENT_ID = "logo"


def _subtype(content_type: str) -> str:
    """Subtipo MIME del adjunto (`application/<subtipo>`). Por defecto `pdf`."""
    parts = (content_type or "").split("/", 1)
    return parts[1].strip() or "pdf" if len(parts) == 2 else "pdf"


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

    def send(
        self,
        *,
        subject: str,
        html: str,
        text: str,
        to: str,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        raw = self._build_raw_message(
            subject=subject, html=html, text=text, to=to, attachments=attachments
        )
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

    def _build_raw_message(
        self,
        *,
        subject: str,
        html: str,
        text: str,
        to: str,
        attachments: Sequence[EmailAttachment] = (),
    ) -> str:
        related = MIMEMultipart("related")
        related["Subject"] = subject
        related["From"] = self._sender
        related["To"] = to

        alternative = MIMEMultipart("alternative")
        related.attach(alternative)
        alternative.attach(MIMEText(text, "plain", "utf-8"))
        alternative.attach(MIMEText(html, "html", "utf-8"))

        image = MIMEImage(self._logo, "png")
        image.add_header("Content-ID", f"<{LOGO_CONTENT_ID}>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        related.attach(image)

        if not attachments:
            return related.as_string()

        message = MIMEMultipart("mixed")
        message["Subject"] = subject
        message["From"] = self._sender
        message["To"] = to
        message.attach(related)
        for attachment in attachments:
            part = MIMEApplication(attachment.content, _subtype=_subtype(attachment.content_type))
            part.add_header("Content-Disposition", "attachment", filename=attachment.filename)
            message.attach(part)

        return message.as_string()
