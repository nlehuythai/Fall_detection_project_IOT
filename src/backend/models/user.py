
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    String,
    Text,
    DateTime,
    func,
    Index
)

from src.backend.db import Base


class User(Base):
    __tablename__ = "users"

    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # Personal information
    full_name = Column(
        String(150),
        nullable=False
    )

    email = Column(String(255), nullable=False)

    password_hash = Column(
        Text,
        nullable=False
    )

    # Account information
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    is_active = Column(
        Boolean,
        nullable=False,
        server_default="true"
    )
    role = Column(
        String(20),
        nullable=False,
        server_default="user"
    )
    __table_args__ = (
        Index(
            "uq_users_email_lower",
            func.lower(email),
            unique=True
        ),
    )