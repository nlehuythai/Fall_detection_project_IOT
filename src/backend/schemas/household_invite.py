from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class HouseholdInviteCreate(BaseModel):
    email: EmailStr

    role: str = Field(
        default="member",
        pattern="^(admin|member)$"
    )


class HouseholdInviteResponse(BaseModel):
    id: int
    household_id: int
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)