
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class TelegramBotConnect(BaseModel):
    bot_token: str


class TelegramBotResponse(BaseModel):
    id: int
    household_id: int
    bot_username: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
