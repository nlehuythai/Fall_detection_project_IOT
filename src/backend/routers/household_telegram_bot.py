import requests

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.dependencies import get_current_user

from src.backend.models.user import User
from src.backend.models.household import Household
from src.backend.models.household_member import HouseholdMember
from src.backend.models.household_telegram_bot import HouseholdTelegramBot

from src.backend.schemas.household_telegram_bot import (
    TelegramBotConnect,
    TelegramBotResponse
)

from src.backend.telegram_security import encrypt_telegram_token


router = APIRouter(
    prefix="/households",
    tags=["Household Telegram Bots"]
)
def get_household_owner(
    household_id: int,
    current_user: User,
    db: Session
):
    # Kiểm tra hộ gia đình có tồn tại không
    household = db.query(Household).filter(
        Household.id == household_id
    ).first()

    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Kiểm tra thành viên trong hộ
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Chỉ owner được quản lý Telegram Bot
    if membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owner can manage Telegram Bot"
        )

    return household
@router.post(
    "/{household_id}/telegram-bot",
    response_model=TelegramBotResponse,
    status_code=status.HTTP_201_CREATED
)
def connect_telegram_bot(
    household_id: int,
    data: TelegramBotConnect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Kiểm tra quyền owner
    get_household_owner(
        household_id,
        current_user,
        db
    )

    # 2. Kiểm tra Bot Token với Telegram
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{data.bot_token}/getMe",
            timeout=10
        )

        telegram_data = response.json()

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot connect to Telegram API"
        )

    # 3. Token không hợp lệ
    if not telegram_data.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram Bot Token"
        )

    bot_username = telegram_data["result"]["username"]

    # 4. Kiểm tra Bot đã được hộ gia đình khác sử dụng chưa
    existing_bot = db.query(HouseholdTelegramBot).filter(
        HouseholdTelegramBot.bot_username == bot_username,
        HouseholdTelegramBot.household_id != household_id
    ).first()

    if existing_bot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Telegram Bot is already connected to another household"
        )

    # 5. Mã hóa Token
    encrypted_token = encrypt_telegram_token(data.bot_token)

    # 6. Kiểm tra hộ đã có Bot chưa
    bot = db.query(HouseholdTelegramBot).filter(
        HouseholdTelegramBot.household_id == household_id
    ).first()

    if bot:
        # Cập nhật Bot hiện tại
        bot.bot_token_encrypted = encrypted_token
        bot.bot_username = bot_username
        bot.is_active = True

    else:
        # Tạo Bot mới
        bot = HouseholdTelegramBot(
            household_id=household_id,
            bot_token_encrypted=encrypted_token,
            bot_username=bot_username,
            is_active=True
        )

        db.add(bot)

    try:
        db.commit()
        db.refresh(bot)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save Telegram Bot"
        )

    return bot
@router.get(
    "/{household_id}/telegram-bot",
    response_model=TelegramBotResponse
)
def get_telegram_bot(
    household_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Kiểm tra người dùng có thuộc hộ gia đình không
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == current_user.id
    ).first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # 2. Lấy thông tin Bot
    bot = db.query(HouseholdTelegramBot).filter(
        HouseholdTelegramBot.household_id == household_id
    ).first()

    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram Bot has not been connected"
        )

    return bot
@router.delete(
    "/{household_id}/telegram-bot",
    status_code=status.HTTP_200_OK
)
def disconnect_telegram_bot(
    household_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Kiểm tra quyền owner
    get_household_owner(
        household_id,
        current_user,
        db
    )

    # 2. Tìm Bot
    bot = db.query(HouseholdTelegramBot).filter(
        HouseholdTelegramBot.household_id == household_id
    ).first()

    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram Bot has not been connected"
        )

    # 3. Xóa cấu hình Bot
    db.delete(bot)
    db.commit()

    return {
        "message": "Telegram Bot disconnected successfully"
    }