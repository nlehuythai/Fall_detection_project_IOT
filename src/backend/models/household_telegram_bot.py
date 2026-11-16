
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship

from src.backend.db import Base


class HouseholdTelegramBot(Base):
    __tablename__ = "household_telegram_bots"

    id = Column(Integer, primary_key=True, index=True)

    household_id = Column(
        Integer,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    bot_token_encrypted = Column(Text, nullable=False)

    bot_username = Column(String(100), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    household = relationship(
        "Household",
        backref="telegram_bot"
    )
