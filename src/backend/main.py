
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.routers.auth import router as auth_router
from src.backend.routers.households import router as households_router
from src.backend.routers.cameras import router as cameras_router
from src.backend.routers.events import router as events_router
from src.backend.routers.household_invites import router as household_invites_router
from src.backend.routers.telegram_chats import (
    router as telegram_chats_router
)

from src.backend.services.camera_status_sync import sync_camera_statuses


# Background task: synchronize camera statuses
async def camera_status_sync_loop():
    while True:
        try:
            updated_count = await asyncio.to_thread(
                sync_camera_statuses
            )

            if updated_count > 0:
                print(
                    f"[CAMERA SYNC] Updated {updated_count} camera(s)"
                )

        except Exception as e:
            print(f"[CAMERA SYNC] Error: {e}")

        await asyncio.sleep(5)


# FastAPI lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[BACKEND] Starting camera status synchronization...")

    sync_task = asyncio.create_task(
        camera_status_sync_loop()
    )

    yield

    print("[BACKEND] Stopping camera status synchronization...")

    sync_task.cancel()

    try:
        await sync_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Fall Detection API",
    description="Backend quản lý hệ thống giám sát té ngã",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routers
app.include_router(auth_router)
app.include_router(households_router)
app.include_router(cameras_router)
app.include_router(events_router)
app.include_router(household_invites_router)
app.include_router(telegram_chats_router)


@app.get("/")
def root():
    return {
        "message": "Fall Detection API is running",
        "status": "success"
    }


@app.get("/health/db")
def check_database(db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("SELECT current_database(), NOW()")
        ).fetchone()

        return {
            "status": "success",
            "message": "PostgreSQL connection successful",
            "database": result[0],
            "server_time": result[1].isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )
