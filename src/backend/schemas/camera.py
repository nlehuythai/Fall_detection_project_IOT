from pydantic import BaseModel, Field, ConfigDict


class CameraCreate(BaseModel):
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

class CameraResponse(BaseModel):
    id: int
    household_id: int
    device_id: str
    camera_name: str
    stream_url: str | None = None
    status: str
    monitoring_enabled: bool = False

    model_config = ConfigDict(from_attributes=True)
class CameraCreatedResponse(CameraResponse):
    device_api_key: str