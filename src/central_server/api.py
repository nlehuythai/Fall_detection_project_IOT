
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Depends
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import time
from src.central_server.main import CentralAIServer


# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
class CameraResetRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)

# Request schema
class CameraStartRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    stream_url: str = Field(min_length=1, max_length=500)

# Initialize Central AI Server
server = CentralAIServer()
def generate_mjpeg_stream(camera_id: int):
    camera = server.camera_manager.get_camera(camera_id)

    if camera is None:
        return

    frame_buffer = camera.frame_buffer
    last_frame_id = -1

    while camera.is_running:
        result = frame_buffer.get_latest_frame(
            last_frame_id=last_frame_id,
            timeout=2.0
        )

        if result is None:
            continue

        frame_id, jpeg_bytes = result
        last_frame_id = frame_id

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg_bytes
            + b"\r\n"
        )

# Internal API authentication
def verify_internal_api_key(
    x_internal_api_key: str = Header(default="")
):
    expected_key = os.getenv("CENTRAL_AI_API_KEY")

    if (
        not expected_key
        or not secrets.compare_digest(
            x_internal_api_key,
            expected_key
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid internal API key"
        )


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    server.initialize()

    app.state.central_server = server

    yield

    server.shutdown()


app = FastAPI(
    title="Central AI Server",
    description="Internal API for Fall Detection Camera Management",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def root():
    return {
        "message": "Central AI Server is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Central AI Server"
    }


# Start camera
@app.post(
    "/internal/cameras/{camera_id}/start",
    dependencies=[Depends(verify_internal_api_key)]
)
def start_camera(
    camera_id: int,
    payload: CameraStartRequest
):
    camera = server.camera_manager.get_camera(camera_id)

    if camera is None:
        added = server.add_camera(
            camera_id=camera_id,
            device_id=payload.device_id,
            stream_url=payload.stream_url
        )

        if not added:
            raise HTTPException(
                status_code=409,
                detail="Could not add camera"
            )

    else:
        if camera.stream_url != payload.stream_url:
            if camera.is_running:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot change stream URL while camera is running"
                )

            camera.stream_url = payload.stream_url

    success = server.start_camera(camera_id)

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to camera"
        )

    camera = server.camera_manager.get_camera(camera_id)

    return {
        "camera_id": camera_id,
        "status": camera.status,
        "monitoring_enabled": camera.is_running,
        "message": "Camera started successfully"
    }


# Stop camera
@app.post(
    "/internal/cameras/{camera_id}/stop",
    dependencies=[Depends(verify_internal_api_key)]
)
def stop_camera(camera_id: int):

    camera = server.camera_manager.get_camera(camera_id)

    # Camera chưa được đăng ký trong AI Server
    if camera is None:
        return {
            "camera_id": camera_id,
            "status": "offline",
            "monitoring_enabled": False,
            "message": "Camera was not registered; nothing to stop"
        }

    # Camera đã tồn tại, tiến hành dừng
    success = server.stop_camera(camera_id)

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Could not stop camera safely"
        )

    return {
        "camera_id": camera_id,
        "status": "offline",
        "monitoring_enabled": False,
        "message": "Camera stopped successfully"
    }

# Get all cameras
@app.get(
    "/internal/cameras",
    dependencies=[Depends(verify_internal_api_key)]
)
def get_cameras():

    cameras = server.camera_manager.get_all_cameras()

    return [
        {
            "camera_id": camera_id,
            "status": camera.status,
            "monitoring_enabled": camera.is_running
        }
        for camera_id, camera in cameras.items()
    ]
# Live camera streaming
@app.get(
    "/internal/cameras/{camera_id}/stream",
    dependencies=[Depends(verify_internal_api_key)]
)
def stream_camera(camera_id: int):

    camera = server.camera_manager.get_camera(camera_id)

    if camera is None:
        raise HTTPException(
            status_code=404,
            detail="Camera not found"
        )

    if not camera.is_running:
        raise HTTPException(
            status_code=409,
            detail="Camera monitoring is not running"
        )

    return StreamingResponse(
        generate_mjpeg_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
@app.post(
    "/internal/cameras/{camera_id}/reset-after-resolved",
    dependencies=[Depends(verify_internal_api_key)]
)
def reset_camera_after_resolved(
    camera_id: int,
    payload: CameraResetRequest
):
    if camera_id != payload.camera_id:
        raise HTTPException(
            status_code=400,
            detail="Camera ID mismatch"
        )

    success = server.reset_camera_after_resolved(
        camera_id=camera_id,
        event_id=payload.event_id
    )

    if not success:
        raise HTTPException(
            status_code=409,
            detail="Camera or event state mismatch"
        )

    return {
        "status": "success",
        "message": "Camera AI state reset successfully",
        "camera_id": camera_id,
        "event_id": payload.event_id
    }