from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    func,
)

from src.backend.db import Base


class HouseholdTelegramChat(Base):
    __tablename__ = "household_telegram_chats"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    household_id = Column(
        BigInteger,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    telegram_chat_id = Column(
        BigInteger,
        nullable=True
    )

    link_code_hash = Column(
        String(64),
        nullable=True
    )

    link_code_expires_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    linked_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )