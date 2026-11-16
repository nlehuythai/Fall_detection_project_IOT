from sqlalchemy import (
    BigInteger,
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from src.backend.db import Base


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    household_id = Column(
        BigInteger,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False
    )

    invited_by = Column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False
    )

    email = Column(String(255), nullable=False)

    role = Column(
        String(20),
        nullable=False,
        default="member",
        server_default="member"
    )

    token_hash = Column(Text, nullable=False, unique=True)

    expires_at = Column(DateTime(timezone=True), nullable=False)

    accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'member')",
            name="chk_invite_role"
        ),
    )