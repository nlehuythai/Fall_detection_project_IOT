from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class FallEventCreate(BaseModel):
    event_id: str = Field(
        min_length=1,
        max_length=100
    )

    occurred_at: datetime

    fall_duration_seconds: float | None = Field(
        default=None,
        ge=0
    )

    average_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1
    )

    snapshot_key: str | None = None


class FallEventResponse(BaseModel):
    id: int
    event_id: str
    household_id: int
    camera_id: int
    occurred_at: datetime
    fall_duration_seconds: float | None
    average_confidence: float | None
    snapshot_key: str | None
    acknowledged: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)