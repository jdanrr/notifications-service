"""Implementacion SQL del puerto de notification_log (idempotencia por event_id)."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from notifications.domain.notification_log import NotificationLog, NotificationStatus
from notifications.infrastructure.outbound.persistence.models import NotificationLogRow


class SqlNotificationLogRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def has_been_sent(self, event_id: str) -> bool:
        """True solo si ese event_id ya produjo un envio con exito."""
        with self._session_factory() as session:
            status = session.execute(
                select(NotificationLogRow.status).where(NotificationLogRow.event_id == event_id)
            ).first()
            return status is not None and status[0] == NotificationStatus.SENT

    def record(self, log: NotificationLog) -> None:
        """Inserta el registro. Si el event_id ya existe (SQS entrego dos veces),
        actualiza el estado en lugar de fallar."""
        with self._session_factory() as session:
            session.add(
                NotificationLogRow(
                    event_id=log.event_id,
                    correlation_id=log.correlation_id,
                    channel=log.channel,
                    template=log.template,
                    status=log.status,
                    created_at=log.created_at,
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                session.execute(
                    update(NotificationLogRow)
                    .where(NotificationLogRow.event_id == log.event_id)
                    .values(
                        correlation_id=log.correlation_id,
                        template=log.template,
                        status=log.status,
                    )
                )
                session.commit()
