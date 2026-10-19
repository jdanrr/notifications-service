"""Tabla notification_log (SQLAlchemy). Equivale a la entidad de dominio."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from notifications.infrastructure.outbound.persistence.database import Base


class NotificationLogRow(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Unica: es la clave de idempotencia frente a entregas dobles de SQS.
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(16))
    template: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    # Motivo del fallo (p. ej. "expired"). NULL en envios exitosos.
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
