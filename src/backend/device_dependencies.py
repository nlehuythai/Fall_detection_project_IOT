import hashlib
import hmac

from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import Camera


def get_current_camera(
    x_device_id: str = Header(..., alias="X-Device-ID"),
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db)
) -> Camera:

    camera = db.query(Camera).filter(
        Camera.device_id == x_device_id
    ).first()

    if camera is None or not camera.device_key_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials"
        )

    received_hash = hashlib.sha256(
        x_device_key.encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(
        received_hash,
        camera.device_key_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials"
        )

    return camera