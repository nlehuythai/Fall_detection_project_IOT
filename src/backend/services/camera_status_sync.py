
from src.backend.db import SessionLocal
from src.backend.models import Camera
from src.backend.services.central_ai_service import get_cameras


def sync_camera_statuses():
    """
    Đồng bộ trạng thái camera từ Central AI Server
    về PostgreSQL.
    """

    # 1. Lấy trạng thái từ Central AI Server
    central_cameras = get_cameras()

    # Tạo dictionary để tra cứu nhanh theo camera_id
    central_status = {
        item["camera_id"]: item["status"]
        for item in central_cameras
    }

    db = SessionLocal()

    try:
        # 2. Lấy tất cả camera trong PostgreSQL
        cameras = db.query(Camera).all()

        updated_count = 0

        for camera in cameras:

            # 3. Camera không có trong Central AI Server
            # được xem là offline
            new_status = central_status.get(
                camera.id,
                "offline"
            )

            # 4. Chỉ cập nhật khi trạng thái thay đổi
            if camera.status != new_status:
                camera.status = new_status
                updated_count += 1

        # 5. Lưu thay đổi
        if updated_count > 0:
            db.commit()

        return updated_count

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
