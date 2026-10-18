"""Tipos compartidos del sobre de eventos (metadata)."""

from pydantic import BaseModel, ConfigDict, Field


class EventMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_version: str | None = Field(default=None, alias="eventVersion")
    occurred_at: str | None = Field(default=None, alias="occurredAt")
    correlation_id: str | None = Field(default=None, alias="correlationId")
