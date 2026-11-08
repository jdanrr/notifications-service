"""Fake del puerto AttachmentProviderPort: devuelve bytes en memoria."""

from notifications.application.ports.email_sender_port import EmailAttachment


class FakeAttachmentProvider:
    def __init__(
        self,
        content: bytes = b"%PDF-1.4 fake",
        content_type: str = "application/pdf",
    ) -> None:
        self.content = content
        self.content_type = content_type
        self.error: Exception | None = None
        self.requested: list[tuple[str, str]] = []

    def fetch(self, *, bucket: str, key: str) -> EmailAttachment:
        self.requested.append((bucket, key))
        if self.error is not None:
            raise self.error
        filename = key.rsplit("/", 1)[-1] or key
        return EmailAttachment(
            filename=filename, content=self.content, content_type=self.content_type
        )
