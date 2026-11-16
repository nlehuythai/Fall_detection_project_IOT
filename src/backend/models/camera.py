
from sqlalchemy import (
    BigInteger,
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)

from src.backend.db import Base


class Camera(Base):
    __tablename__ = "cameras"

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

    device_id = Column(
        String(100),
        nullable=False,
        unique=True
    )

    camera_name = Column(
        String(150),
        nullable=False
    )

    device_key_hash = Column(
        String,
        nullable=True
    )

    status = Column(
        String(20),
        nullable=False,
        default="offline",
        server_default="offline"
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "id",
            "household_id",
            name="uq_camera_household"
        ),
        CheckConstraint(
            "status IN ('online', 'offline', 'maintenance')",
            name="chk_camera_status"
        ),
    )
