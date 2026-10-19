"""Fake en memoria del puerto de notification_log (idempotencia por event_id)."""

from notifications.domain.notification_log import NotificationLog, NotificationStatus


class InMemoryNotificationLogRepository:
    def __init__(self) -> None:
        self._sent: set[str] = set()
        self.records: list[NotificationLog] = []

    def has_been_sent(self, event_id: str) -> bool:
        return event_id in self._sent

    def record(self, log: NotificationLog) -> None:
        self.records.append(log)
        if log.status == NotificationStatus.SENT:
            self._sent.add(log.event_id)

    @property
    def sent_event_ids(self) -> set[str]:
        return set(self._sent)

    @property
    def failures(self) -> list[NotificationLog]:
        """Registros con status=failed (para assert de motivos)."""
        return [r for r in self.records if r.status == NotificationStatus.FAILED]
