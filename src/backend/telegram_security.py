import os
from pathlib import Path

from dotenv import load_dotenv
from cryptography.fernet import Fernet


# Xác định thư mục gốc của project
ROOT_DIR = Path(__file__).resolve().parents[2]

# Đọc biến môi trường từ file .env
load_dotenv(ROOT_DIR / ".env")


def get_fernet():
    """
    Khởi tạo Fernet để mã hóa và giải mã Telegram Bot Token.
    """
    encryption_key = os.getenv("TELEGRAM_ENCRYPTION_KEY")

    if not encryption_key:
        raise RuntimeError(
            "TELEGRAM_ENCRYPTION_KEY chưa được cấu hình trong .env"
        )

    return Fernet(encryption_key.encode())


def encrypt_telegram_token(token: str) -> str:
    """
    Mã hóa Telegram Bot Token trước khi lưu database.
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(token.encode())

    return encrypted.decode()


def decrypt_telegram_token(encrypted_token: str) -> str:
    """
    Giải mã Telegram Bot Token khi Backend cần sử dụng.
    """
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_token.encode())

    return decrypted.decode()