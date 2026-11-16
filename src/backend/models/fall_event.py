
from sqlalchemy import (
    BigInteger,
    Column,
    String,
    DateTime,
    Numeric,
    Boolean,
    ForeignKeyConstraint,
    Text,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from src.backend.db import Base


class FallEvent(Base):
    __tablename__ = "fall_events"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    event_id = Column(
        String(100),
        nullable=False,
        unique=True
    )

    household_id = Column(
        BigInteger,
        nullable=False
    )

    camera_id = Column(
        BigInteger,
        nullable=False
    )

    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    fall_duration_seconds = Column(
        Numeric(8, 2),
        nullable=True
    )

    average_confidence = Column(
        Numeric(5, 4),
        nullable=True
    )

    snapshot_key = Column(
        Text,
        nullable=True
    )

    acknowledged = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )

    raw_payload = Column(
        JSONB,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["camera_id", "household_id"],
            ["cameras.id", "cameras.household_id"],
            name="fk_event_camera_household"
        ),
        CheckConstraint(
            "average_confidence IS NULL OR average_confidence BETWEEN 0 AND 1",
            name="chk_event_confidence"
        ),
        CheckConstraint(
            "fall_duration_seconds IS NULL OR fall_duration_seconds >= 0",
            name="chk_event_duration"
        ),
    )
