"""Tipos compartidos del sobre de eventos (metadata)."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventMetadata(BaseModel):
    """metadata del evento. Todos los campos son obligatorios."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_version: str = Field(alias="eventVersion")
    occurred_at: AwareDatetime = Field(alias="occurredAt")
    correlation_id: str = Field(alias="correlationId")
