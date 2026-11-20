from pydantic import BaseModel, Field


class CameraUpdate(BaseModel):
    device_id: str = Field(
        min_length=1,
        max_length=100
    )

    camera_name: str = Field(
        min_length=2,
        max_length=150
    )

    stream_url: str | None = Field(
        default=None,
        max_length=500
    )