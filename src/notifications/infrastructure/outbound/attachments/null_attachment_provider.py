"""Adaptador nulo: se usa cuando no hay backend de adjuntos configurado.

Cualquier descarga falla en seco como error permanente: mejor descartar el
mensaje con traza que enviar el correo sin el PDF adjunto.
"""

from notifications.application.ports.email_sender_port import EmailAttachment
from notifications.domain.errors import PermanentNotificationError


class NullAttachmentProvider:
    def fetch(self, *, bucket: str, key: str) -> EmailAttachment:
        raise PermanentNotificationError("proveedor de adjuntos no configurado")
