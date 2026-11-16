
from sqlalchemy import (
    BigInteger,
    Column,
    String,
    DateTime,
    ForeignKey,
    func,
)

from src.backend.db import Base


class HouseholdMember(Base):
    __tablename__ = "household_members"

    # Foreign Keys
    household_id = Column(
        BigInteger,
        ForeignKey("households.id", ondelete="CASCADE"),
        primary_key=True
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Member role
    role = Column(
        String(20),
        nullable=False,
        default="member",
        server_default="member"
    )

    # Join time
    joined_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
