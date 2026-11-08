"""Puerto: descarga de adjuntos (PDFs de Documents en S3).

El caso de uso pide el archivo por (bucket, key) del evento y el adaptador
devuelve el contenido listo para adjuntar al correo.
"""

from typing import Protocol, runtime_checkable

from notifications.application.ports.email_sender_port import EmailAttachment


@runtime_checkable
class AttachmentProviderPort(Protocol):
    def fetch(self, *, bucket: str, key: str) -> EmailAttachment:
        """Descarga el objeto y lo devuelve como adjunto.

        `filename` trae un valor por defecto (último segmento del key); el
        caso de uso lo reemplaza por el `fileName` que trae el evento.
        Lanza PermanentNotificationError si la referencia es inválida o el
        objeto no existe, TransientNotificationError si es un fallo
        reintentable de red/servicio.
        """
        ...
