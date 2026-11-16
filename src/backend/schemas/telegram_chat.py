
from pydantic import BaseModel
from datetime import datetime


class TelegramLinkCodeResponse(BaseModel):
    link_code: str
    expires_at: datetime
    bot_username: str