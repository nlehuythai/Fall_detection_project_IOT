
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128
    )


class UserUpdate(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=150
    )


class PasswordChange(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128
    )

    new_password: str = Field(
        min_length=8,
        max_length=128
    )
