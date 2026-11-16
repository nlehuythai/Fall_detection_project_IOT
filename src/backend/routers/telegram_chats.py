import secrets
import hashlib

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.dependencies import get_current_user

from src.backend.models.user import User
from src.backend.models.household_member import HouseholdMember
from src.backend.models.household_telegram_bot import HouseholdTelegramBot
from src.backend.models.household_telegram_chat import HouseholdTelegramChat

from src.backend.schemas.telegram_chat import TelegramLinkCodeResponse


router = APIRouter(
    prefix="/households",
    tags=["Telegram Chat Linking"]
)
@router.post(
    "/{household_id}/telegram-link-code",
    response_model=TelegramLinkCodeResponse
)
def create_telegram_link_code(
    household_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Kiểm tra thành viên có thuộc hộ gia đình không
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # 2. Lấy Telegram Bot của hộ gia đình
    bot = db.query(HouseholdTelegramBot).filter(
        HouseholdTelegramBot.household_id == household_id,
        HouseholdTelegramBot.is_active == True
    ).first()

    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram Bot has not been connected"
        )

    # 3. Tạo mã liên kết ngẫu nhiên
    link_code = secrets.token_urlsafe(24)

    # 4. Băm mã bằng SHA-256
    link_code_hash = hashlib.sha256(
        link_code.encode()
    ).hexdigest()

    # 5. Thiết lập thời hạn 10 phút
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    # 6. Kiểm tra bản ghi liên kết của thành viên
    telegram_chat = db.query(HouseholdTelegramChat).filter(
        HouseholdTelegramChat.household_id == household_id,
        HouseholdTelegramChat.user_id == current_user.id
    ).first()

    if telegram_chat:
        # Cấp mã mới, giữ nguyên Chat ID nếu đã liên kết
        telegram_chat.link_code_hash = link_code_hash
        telegram_chat.link_code_expires_at = expires_at

    else:
        telegram_chat = HouseholdTelegramChat(
            household_id=household_id,
            user_id=current_user.id,
            link_code_hash=link_code_hash,
            link_code_expires_at=expires_at
        )

        db.add(telegram_chat)

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Telegram link code"
        )

    # 7. Trả mã liên kết cho Website
    return TelegramLinkCodeResponse(
        link_code=link_code,
        expires_at=expires_at,
        bot_username=bot.bot_username
    )