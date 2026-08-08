from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class Entity(ApiModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventEnvelope(Entity):
    event_type: str
    organization_id: UUID
    actor_type: str
    actor_id: UUID
    correlation_id: UUID = Field(default_factory=uuid4)
    payload: dict

