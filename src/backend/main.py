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
from src.backend.routers.household_telegram_bot import (
    router as household_telegram_bots_router
)
from src.backend.routers.telegram_chats import (
    router as telegram_chats_router
)
app = FastAPI(
    title="Fall Detection API",
    description="Backend quản lý hệ thống giám sát té ngã",
    version="1.0.0"
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

# Đăng ký Auth Router
app.include_router(auth_router)
app.include_router(households_router)
app.include_router(cameras_router)
app.include_router(events_router)
app.include_router(household_invites_router)
app.include_router(household_telegram_bots_router)
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