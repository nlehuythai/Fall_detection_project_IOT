from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from pathlib import Path
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.dependencies import get_current_user
from src.backend.models import User, FallEvent, HouseholdMember
from src.backend.schemas import FallEventResponse

from src.backend.device_dependencies import get_current_camera
from src.backend.schemas import FallEventCreate
from src.backend.models import Camera
router = APIRouter(prefix="/households", tags=["Fall Events"])

# Project root: D:/Iot_project/aaa
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Snapshot storage directory
SNAPSHOT_ROOT = (PROJECT_ROOT / "data" / "snapshots").resolve()
@router.get(
    "/{household_id}/events",
    response_model=list[FallEventResponse]
)
def get_fall_events(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra quyền thành viên
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Lấy lịch sử té ngã mới nhất trước
    events = db.query(FallEvent).filter(
        FallEvent.household_id == household_id
    ).order_by(
        FallEvent.occurred_at.desc()
    ).all()

    return events
@router.post(
    "/devices/events",
    response_model=FallEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Device Events"]
)
def create_device_fall_event(
    event_data: FallEventCreate,
    db: Session = Depends(get_db),
    camera: Camera = Depends(get_current_camera)
):
    # Kiểm tra event_id đã tồn tại
    existing_event = db.query(FallEvent).filter(
        FallEvent.event_id == event_data.event_id
    ).first()

    if existing_event:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event ID already exists"
        )

    new_event = FallEvent(
        event_id=event_data.event_id,
        household_id=camera.household_id,
        camera_id=camera.id,
        occurred_at=event_data.occurred_at,
        fall_duration_seconds=event_data.fall_duration_seconds,
        average_confidence=event_data.average_confidence,
        snapshot_key=event_data.snapshot_key,
        acknowledged=False
    )

    db.add(new_event)

    try:
        db.commit()
        db.refresh(new_event)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save fall event"
        )

    return new_event
@router.patch("/{household_id}/events/{event_id}/acknowledge")
def acknowledge_fall_event(
    household_id: int,
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check household membership
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Find fall event
    event = db.query(FallEvent).filter(
        FallEvent.id == event_id,
        FallEvent.household_id == household_id
    ).first()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fall event not found"
        )

    # Acknowledge event
    if event.acknowledged:
        return {
            "status": "success",
            "message": "Event already acknowledged",
            "event_id": event.id,
            "acknowledged": True
        }

    event.acknowledged = True
    db.commit()
    db.refresh(event)

    return {
        "status": "success",
        "message": "Fall event acknowledged successfully",
        "event_id": event.id,
        "acknowledged": event.acknowledged
    }

@router.get(
    "/{household_id}/events/{event_id}",
    response_model=FallEventResponse
)
def get_fall_event_detail(
    household_id: int,
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check household membership
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Find fall event
    event = db.query(FallEvent).filter(
        FallEvent.id == event_id,
        FallEvent.household_id == household_id
    ).first()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fall event not found"
        )

    return event
@router.get(
    "/{household_id}/events/{event_id}/snapshot"
)
def get_fall_event_snapshot(
    household_id: int,
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Check household membership
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # 2. Find event
    event = db.query(FallEvent).filter(
        FallEvent.id == event_id,
        FallEvent.household_id == household_id
    ).first()

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fall event not found"
        )

    # 3. Check snapshot key
    if not event.snapshot_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not available"
        )

    # 4. Resolve safe file path
    try:
        relative_key = event.snapshot_key.replace("\\", "/")
        parts = Path(relative_key).parts

        if (
            Path(relative_key).is_absolute()
            or ".." in parts
        ):
            raise ValueError("Invalid snapshot path")

        snapshot_path = SNAPSHOT_ROOT.joinpath(
            *parts
        ).resolve()

        # Prevent path traversal
        snapshot_path.relative_to(SNAPSHOT_ROOT)

    except (ValueError, OSError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid snapshot path"
        )

    # 5. Check file
    if not snapshot_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot file not found"
        )

    # 6. Return image
    return FileResponse(
        path=str(snapshot_path),
        media_type="image/jpeg",
        filename=snapshot_path.name
    )