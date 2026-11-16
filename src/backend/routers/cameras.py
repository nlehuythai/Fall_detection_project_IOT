from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import secrets
import hashlib

from src.backend.db import get_db
from src.backend.dependencies import get_current_user
from src.backend.models import User, Camera, HouseholdMember
from src.backend.schemas import (
    CameraCreate,
    CameraResponse,
    CameraCreatedResponse,
    CameraUpdate,
)

router = APIRouter(prefix="/households", tags=["Cameras"])


@router.post(
    "/{household_id}/cameras",
    response_model=CameraCreatedResponse,
    status_code=status.HTTP_201_CREATED
)
def create_camera(
    household_id: int,
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Generate device API key
    device_api_key = secrets.token_urlsafe(32)

    # Store only the SHA-256 hash
    device_key_hash = hashlib.sha256(
        device_api_key.encode("utf-8")
    ).hexdigest()

    new_camera = Camera(
        household_id=household_id,
        device_id=camera_data.device_id,
        camera_name=camera_data.camera_name,
        device_key_hash=device_key_hash,
        status="offline"
    )

    db.add(new_camera)

    try:
        db.commit()
        db.refresh(new_camera)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device ID already exists"
        )

    return {
        "id": new_camera.id,
        "household_id": new_camera.household_id,
        "device_id": new_camera.device_id,
        "camera_name": new_camera.camera_name,
        "status": new_camera.status,
        "device_api_key": device_api_key
    }    
@router.get(
    "/{household_id}/cameras",
    response_model=list[CameraResponse]
)
def get_cameras(
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

    # Lấy danh sách camera thuộc hộ gia đình
    cameras = db.query(Camera).filter(
        Camera.household_id == household_id
    ).order_by(Camera.id.asc()).all()

    return cameras
@router.post(
    "/{household_id}/cameras/{camera_id}/regenerate-key"
)
def regenerate_camera_key(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    # Generate a new API key
    device_api_key = secrets.token_urlsafe(32)

    # Store only its SHA-256 hash
    camera.device_key_hash = hashlib.sha256(
        device_api_key.encode("utf-8")
    ).hexdigest()

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not regenerate camera key"
        )

    return {
        "message": "Camera API key regenerated successfully",
        "device_id": camera.device_id,
        "device_api_key": device_api_key
    }
@router.get(
    "/{household_id}/cameras/{camera_id}",
    response_model=CameraResponse
)
def get_camera_detail(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Tìm camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    return camera
@router.patch(
    "/{household_id}/cameras/{camera_id}",
    response_model=CameraResponse
)
def update_camera(
    household_id: int,
    camera_id: int,
    camera_data: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Tìm camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    # Cập nhật tên camera
    camera.camera_name = camera_data.camera_name.strip()

    if not camera.camera_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Camera name cannot be empty"
        )

    try:
        db.commit()
        db.refresh(camera)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update camera"
        )

    return camera
@router.delete(
    "/{household_id}/cameras/{camera_id}"
)
def delete_camera(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Tìm camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )

    try:
        db.delete(camera)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete camera"
        )

    return {
        "status": "success",
        "message": "Camera deleted successfully",
        "household_id": household_id,
        "camera_id": camera_id
    }