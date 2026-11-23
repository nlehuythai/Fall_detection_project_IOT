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
from fastapi.responses import StreamingResponse
from src.backend.services.central_ai_service import (
    start_camera as start_ai_camera,
    stop_camera as stop_ai_camera,
    open_camera_stream,
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
        stream_url=camera_data.stream_url,
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
        "stream_url": new_camera.stream_url,
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
    # 1. Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # 2. Tìm camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found"
        )
# Không cho phép cập nhật khi camera đang giám sát
    if camera.monitoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update camera while monitoring is enabled. Please stop monitoring first."
        )
    # 3. Cập nhật thông tin camera
    device_id = camera_data.device_id.strip()
    camera_name = camera_data.camera_name.strip()

    if not device_id or not camera_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Device ID and camera name cannot be empty"
        )

    camera.device_id = device_id
    camera.camera_name = camera_name
    camera.stream_url = (
        camera_data.stream_url.strip()
        if camera_data.stream_url
        else None
    )

    # 4. Lưu database
    try:
        db.commit()
        db.refresh(camera)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device ID already exists"
        )

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
    # Không cho phép xóa khi camera đang giám sát
    if camera.monitoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete camera while monitoring is enabled. Please stop monitoring first."
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

@router.post(
    "/{household_id}/cameras/{camera_id}/start"
)
def start_camera_monitoring(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # 2. Kiểm tra camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=404,
            detail="Camera not found"
        )

    # 3. Kiểm tra stream URL
    if not camera.stream_url:
        raise HTTPException(
            status_code=400,
            detail="Camera stream URL is not configured"
        )

    # 4. Gửi lệnh bật camera đến Central AI Server
    result = start_ai_camera(
        camera_id=camera.id,
        device_id=camera.device_id,
        stream_url=camera.stream_url
    )

    # 5. Chỉ cập nhật database khi AI Server thành công
    camera.monitoring_enabled = True
    camera.status = result["status"]

    try:
        db.commit()
        db.refresh(camera)

    except Exception:
        db.rollback()

        # Cố gắng dừng camera nếu không lưu được database
        try:
            stop_ai_camera(camera_id)
        except HTTPException:
            pass

        raise HTTPException(
            status_code=500,
            detail="Could not update camera monitoring status"
        )

    return {
        "message": "Camera monitoring started successfully",
        "camera_id": camera.id,
        "status": camera.status,
        "monitoring_enabled": camera.monitoring_enabled
    }


@router.post(
    "/{household_id}/cameras/{camera_id}/stop"
)
def stop_camera_monitoring(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print("[DEBUG STOP] Endpoint reached")
    print(f"[DEBUG STOP] household_id={household_id}")
    print(f"[DEBUG STOP] camera_id={camera_id}")
    # 1. Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()
    print(f"[DEBUG STOP] membership={membership}")
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # 2. Kiểm tra camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()
    print(f"[DEBUG STOP] camera={camera}")
    if camera is None:
        raise HTTPException(
            status_code=404,
            detail="Camera not found"
        )

    # 3. Gửi lệnh tắt camera đến Central AI Server
    result = stop_ai_camera(camera_id)
    # 4. Cập nhật database sau khi AI Server xác nhận
    camera.monitoring_enabled = False
    camera.status = result["status"]

    try:
        db.commit()
        db.refresh(camera)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update camera monitoring status"
        )

    return {
        "message": "Camera monitoring stopped successfully",
        "camera_id": camera.id,
        "status": camera.status,
        "monitoring_enabled": camera.monitoring_enabled
    }
@router.get(
    "/{household_id}/cameras/{camera_id}/stream"
)
async def stream_camera(
    household_id: int,
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Kiểm tra thành viên hộ gia đình
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=404,
            detail="Household not found"
        )

    # 2. Kiểm tra camera thuộc hộ gia đình
    camera = db.query(Camera).filter(
        Camera.id == camera_id,
        Camera.household_id == household_id
    ).first()

    if camera is None:
        raise HTTPException(
            status_code=404,
            detail="Camera not found"
        )

    # 3. Kiểm tra trạng thái giám sát
    if not camera.monitoring_enabled:
        raise HTTPException(
            status_code=409,
            detail="Camera monitoring is not enabled"
        )

    # 4. Mở stream từ Central AI Server
    client, response = await open_camera_stream(camera_id)

    # 5. Chuyển tiếp MJPEG về trình duyệt
    async def generate_stream():
        try:
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        generate_stream(),
        media_type=response.headers.get(
            "content-type",
            "multipart/x-mixed-replace; boundary=frame"
        ),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )