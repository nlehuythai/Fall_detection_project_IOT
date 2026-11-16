from pydantic import BaseModel, Field


class CameraUpdate(BaseModel):
    camera_name: str = Field(
        min_length=1,
        max_length=150
    )