
from sqlalchemy import (
    BigInteger,
    Column,
    String,
    DateTime,
    func,
)

from src.backend.db import Base


class Household(Base):
    __tablename__ = "households"

    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # Household information
    household_name = Column(
        String(150),
        nullable=False
    )

    # Creation time
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
