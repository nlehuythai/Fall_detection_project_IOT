import os
import json
import urllib.parse
import urllib.request
import uuid
import hashlib
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests
import paho.mqtt.client as mqtt
from dotenv import load_dotenv


# --------------------------------------------------
# Project path and backend imports
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", ""
).strip()
from src.backend.db import SessionLocal
from src.backend.models import Camera, FallEvent, HouseholdTelegramChat


# --------------------------------------------------
# Configuration
# --------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "esp32/camera/detection")

CLIENT_ID = "Telegram_Alert_Listener"
MAX_PROCESSED_EVENTS = 100
REMINDER_DELAY_SECONDS = 60

telegram_polling = False
fall_events_lock = threading.Lock()

# Key: (household_id, event_identifier)
# Value: event data needed by the reminder worker.
pending_fall_events = {}

# Keep a bounded in-memory set to avoid processing duplicate MQTT messages.
processed_event_keys = set()
processed_event_order = deque()


# --------------------------------------------------
# Shared Telegram Bot
# --------------------------------------------------

def get_shared_telegram_bot():
    """Validate the shared Bot Token and return Telegram Bot information."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Chưa cấu hình TELEGRAM_BOT_TOKEN trong file .env"
        )

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            raise RuntimeError("Telegram Bot Token không hợp lệ.")

        bot_info = data["result"]
        print(
            f"[TELEGRAM] Shared Bot connected: "
            f"@{bot_info.get('username', 'unknown')}"
        )
        return bot_info

    except requests.RequestException as error:
        raise RuntimeError(
            f"Không thể kết nối Telegram API: {error}"
        ) from error


# --------------------------------------------------
# Database helpers
# --------------------------------------------------

def get_household_chat_ids(household_id):
    """Return only Telegram chats linked to the requested household."""
    db = SessionLocal()

    try:
        rows = db.query(
            HouseholdTelegramChat.telegram_chat_id
        ).filter(
            HouseholdTelegramChat.household_id == household_id,
            HouseholdTelegramChat.telegram_chat_id.isnot(None),
            HouseholdTelegramChat.linked_at.isnot(None),
        ).all()

        # Remove duplicates while preserving order.
        return list(dict.fromkeys(str(row[0]) for row in rows))

    finally:
        db.close()


def get_household_id_for_device(device_id):
    """Resolve household_id from the registered camera, never from MQTT payload."""
    if not device_id:
        return None

    db = SessionLocal()

    try:
        camera = db.query(Camera).filter(
            Camera.device_id == str(device_id)
        ).first()

        return camera.household_id if camera else None

    finally:
        db.close()


def get_event_acknowledged(household_id, event_identifier):
    """
    Return True/False from PostgreSQL.
    Return None when the event row has not been found yet.
    """
    db = SessionLocal()

    try:
        event = db.query(FallEvent).filter(
            FallEvent.household_id == household_id,
            FallEvent.event_id == event_identifier,
        ).first()

        if event is None:
            return None

        return bool(event.acknowledged)

    finally:
        db.close()


def acknowledge_event_in_database(household_id, event_identifier):
    """Persist Telegram acknowledgment to the same event row used by Website."""
    db = SessionLocal()

    try:
        event = db.query(FallEvent).filter(
            FallEvent.household_id == household_id,
            FallEvent.event_id == event_identifier,
        ).first()

        if event is None:
            return False, "Không tìm thấy sự kiện trong hộ gia đình này."

        event.acknowledged = True
        db.commit()

        return True, "Đã ghi nhận! Cảm ơn bạn đã tiếp nhận cảnh báo."

    except Exception as error:
        db.rollback()
        print(f"[ACK DATABASE ERROR] {error}")
        return False, "Không thể cập nhật trạng thái xác nhận."

    finally:
        db.close()


def acknowledge_event_for_chat(household_id, event_identifier, chat_id):
    """
    Acknowledge only if:
    1. The event belongs to household_id.
    2. The Telegram chat is linked to that same household.
    """
    db = SessionLocal()

    try:
        linked_chat = db.query(HouseholdTelegramChat).filter(
            HouseholdTelegramChat.household_id == household_id,
            HouseholdTelegramChat.telegram_chat_id == int(chat_id),
            HouseholdTelegramChat.linked_at.isnot(None),
        ).first()

        if linked_chat is None:
            return False, "Bạn chưa liên kết Telegram với hộ gia đình này."

        event = db.query(FallEvent).filter(
            FallEvent.household_id == household_id,
            FallEvent.event_id == event_identifier,
        ).first()

        if event is None:
            return False, "Không tìm thấy cảnh báo trong hộ gia đình này."

        event.acknowledged = True
        db.commit()

        return True, "Đã ghi nhận! Cảm ơn bạn đã tiếp nhận cảnh báo."

    except Exception as error:
        db.rollback()
        print(f"[ACK DATABASE ERROR] {error}")
        return False, "Không thể cập nhật trạng thái xác nhận."

    finally:
        db.close()


# --------------------------------------------------
# Telegram linking
# --------------------------------------------------

def link_telegram_chat(chat_id, link_code):
    """
    Link a Telegram private chat using a one-time Website code.

    The same Telegram chat may be linked to multiple households belonging
    to the same Website user. It cannot be linked to a different Website user.
    """
    db = SessionLocal()

    try:
        link_code_hash = hashlib.sha256(
            link_code.encode("utf-8")
        ).hexdigest()

        telegram_chat = db.query(HouseholdTelegramChat).filter(
            HouseholdTelegramChat.link_code_hash == link_code_hash,
            HouseholdTelegramChat.link_code_expires_at > datetime.now(timezone.utc),
        ).first()

        if telegram_chat is None:
            return False, "Mã liên kết không hợp lệ hoặc đã hết hạn."

        existing_chat = db.query(HouseholdTelegramChat).filter(
            HouseholdTelegramChat.telegram_chat_id == int(chat_id),
            HouseholdTelegramChat.linked_at.isnot(None),
            HouseholdTelegramChat.user_id != telegram_chat.user_id,
        ).first()

        if existing_chat:
            return (
                False,
                "Tài khoản Telegram này đã được liên kết với tài khoản Website khác.",
            )

        telegram_chat.telegram_chat_id = int(chat_id)
        telegram_chat.linked_at = datetime.now(timezone.utc)
        telegram_chat.link_code_hash = None
        telegram_chat.link_code_expires_at = None

        db.commit()
        return True, "Liên kết Telegram thành công!"

    except Exception as error:
        db.rollback()
        print(f"[TELEGRAM LINK ERROR] {error}")
        return False, "Không thể liên kết Telegram."

    finally:
        db.close()


# --------------------------------------------------
# Telegram low-level send helpers
# --------------------------------------------------

def send_telegram_text_to_chat(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def answer_telegram_callback(callback_query_id, message, bot_token):
    url = (
        f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    )
    payload = {
        "callback_query_id": callback_query_id,
        "text": message,
    }

    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result.get("ok", False)

    except Exception as error:
        print(f"[TELEGRAM CALLBACK ERROR] {error}")
        return False


# --------------------------------------------------
# Telegram message handling
# --------------------------------------------------

def handle_telegram_start(message, bot_token):
    """Handle /start link_code from a private chat."""
    chat = message.get("chat", {})
    sender = message.get("from", {})

    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")

    if not chat_id or sender.get("id") != chat_id:
        return

    text = (message.get("text") or "").strip()
    parts = text.split(maxsplit=1)

    if not parts or parts[0].split("@")[0] != "/start":
        return

    if len(parts) != 2:
        reply = (
            "Vui lòng tạo mã liên kết trên Website, "
            "sau đó mở liên kết Telegram từ Website."
        )
    else:
        link_code = parts[1].strip()
        _, reply = link_telegram_chat(
            chat_id=chat_id,
            link_code=link_code,
        )

    try:
        result = send_telegram_text_to_chat(
            bot_token,
            chat_id,
            reply,
        )

        if not result.get("ok"):
            print("[TELEGRAM LINK] Telegram did not accept the reply.")

    except Exception as error:
        print(f"[TELEGRAM LINK SEND ERROR] {error}")


# --------------------------------------------------
# Telegram send functions
# --------------------------------------------------

def send_telegram_message(message, household_id):
    """Send a text message only to linked recipients of one household."""
    if not TELEGRAM_BOT_TOKEN:
        print("[TELEGRAM] Shared Bot Token is missing; message not sent.")
        return

    chat_ids = get_household_chat_ids(household_id)

    if not chat_ids:
        print(
            f"[TELEGRAM] No linked recipients for household {household_id}."
        )
        return

    for chat_id in chat_ids:
        try:
            result = send_telegram_text_to_chat(
                TELEGRAM_BOT_TOKEN,
                chat_id,
                message,
            )

            if result.get("ok"):
                print(
                    f"[TELEGRAM] Message sent to household "
                    f"{household_id}, chat {chat_id}."
                )
            else:
                print(
                    f"[TELEGRAM ERROR] Telegram rejected message "
                    f"for household {household_id}, chat {chat_id}."
                )

        except Exception as error:
            print(f"[TELEGRAM SEND ERROR] {error}")


def send_telegram_photo(
    image_path,
    caption,
    event_identifier,
    household_id,
):
    """Send a fall snapshot only to linked recipients of the event household."""
    if not TELEGRAM_BOT_TOKEN:
        print("[TELEGRAM] Shared Bot Token is missing; photo not sent.")
        return

    chat_ids = get_household_chat_ids(household_id)

    if not chat_ids:
        print(
            f"[TELEGRAM] No linked recipients for household {household_id}."
        )
        return

    image_path = Path(image_path) if image_path else None

    if image_path and not image_path.is_absolute():
        image_path = ROOT_DIR / image_path

    if image_path is None or not image_path.is_file():
        print(f"[SNAPSHOT ERROR] Image not found: {image_path}")
        send_telegram_message(caption, household_id)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    # Include household_id in callback data so the callback can be
    # checked against both the event and the Telegram recipient's membership.
    callback_data = f"ACK|{household_id}|{event_identifier}"

    if len(callback_data.encode("utf-8")) > 64:
        print(
            "[TELEGRAM] Callback data exceeds Telegram's 64-byte limit; "
            "photo will be sent without the acknowledgment button."
        )
        reply_markup = None
    else:
        reply_markup = {
            "inline_keyboard": [[{
                "text": "✅ Đã tiếp nhận cảnh báo",
                "callback_data": callback_data,
            }]]
        }

    for chat_id in chat_ids:
        boundary = "----TelegramBoundary" + uuid.uuid4().hex

        try:
            with image_path.open("rb") as image_file:
                image_data = image_file.read()

            body = []

            def add_field(name, value):
                field = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n'
                    "\r\n"
                    f"{value}\r\n"
                )
                body.append(field.encode("utf-8"))

            add_field("chat_id", chat_id)
            add_field("caption", caption)

            if reply_markup is not None:
                add_field(
                    "reply_markup",
                    json.dumps(reply_markup, ensure_ascii=False),
                )

            photo_header = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; '
                f'filename="{image_path.name}"\r\n'
                "Content-Type: image/jpeg\r\n"
                "\r\n"
            )

            body.append(photo_header.encode("utf-8"))
            body.append(image_data)
            body.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

            request = urllib.request.Request(
                url,
                data=b"".join(body),
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}"
                },
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            if result.get("ok"):
                print(
                    f"[TELEGRAM] Photo sent to household {household_id}, "
                    f"chat {chat_id}."
                )
            else:
                print(
                    f"[TELEGRAM PHOTO ERROR] Telegram rejected photo "
                    f"for household {household_id}, chat {chat_id}."
                )

        except Exception as error:
            print(f"[TELEGRAM PHOTO ERROR] {error}")


# --------------------------------------------------
# Telegram callback handling
# --------------------------------------------------

def handle_telegram_callback(callback, bot_token):
    """Handle ACK callback and enforce household-level access isolation."""
    callback_data = callback.get("data", "")
    callback_id = callback.get("id")

    if not callback_data.startswith("ACK|"):
        return

    parts = callback_data.split("|", 2)

    if len(parts) != 3:
        answer_telegram_callback(
            callback_id,
            "Nút xác nhận không hợp lệ. Vui lòng dùng cảnh báo mới nhất.",
            bot_token,
        )
        return

    try:
        household_id = int(parts[1])
    except (TypeError, ValueError):
        answer_telegram_callback(
            callback_id,
            "Không xác định được hộ gia đình của cảnh báo.",
            bot_token,
        )
        return

    event_identifier = parts[2]
    callback_message = callback.get("message") or {}
    chat = callback_message.get("chat") or {}
    chat_id = chat.get("id")

    if not chat_id:
        answer_telegram_callback(
            callback_id,
            "Không xác định được tài khoản Telegram.",
            bot_token,
        )
        return

    ack_success, ack_reply = acknowledge_event_for_chat(
        household_id=household_id,
        event_identifier=event_identifier,
        chat_id=chat_id,
    )

    if ack_success:
        event_key = (household_id, str(event_identifier))

        with fall_events_lock:
            event_data = pending_fall_events.get(event_key)

            if event_data:
                event_data["acknowledged"] = True
                event_data["acknowledged_by"] = str(chat_id)

        print(
            f"[ACKNOWLEDGED] Event {event_identifier} "
            f"| Household {household_id} | Chat {chat_id}"
        )
        print("[REMINDER] Reminder cancelled for this event.")

    answer_telegram_callback(
        callback_id,
        ack_reply,
        bot_token,
    )


# --------------------------------------------------
# Long polling: exactly one shared Bot polling loop
# --------------------------------------------------

def poll_shared_bot(bot_token, bot_username):
    offset = None

    print(
        f"[TELEGRAM] Starting shared Bot @{bot_username}. "
        "One polling thread for all households."
    )

    while telegram_polling:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

            params = {
                "timeout": 20,
                "allowed_updates": json.dumps([
                    "message",
                    "callback_query",
                ]),
            }

            if offset is not None:
                params["offset"] = offset

            request_url = url + "?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(request_url)

            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            if not result.get("ok"):
                print("[TELEGRAM ERROR] Shared Bot getUpdates failed.")
                time.sleep(3)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message")
                if message:
                    handle_telegram_start(message, bot_token)
                    continue

                callback = update.get("callback_query")
                if callback:
                    handle_telegram_callback(callback, bot_token)

        except Exception as error:
            if telegram_polling:
                print(f"[TELEGRAM POLLING ERROR] Shared Bot: {error}")
                time.sleep(3)

    print("[TELEGRAM] Shared Bot polling stopped.")


# --------------------------------------------------
# Reminder worker: check PostgreSQL before sending reminder
# --------------------------------------------------

def reminder_worker():
    print("[REMINDER] Reminder worker started.")

    while telegram_polling:
        current_time = time.monotonic()
        candidates = []

        with fall_events_lock:
            for event_key, event_data in pending_fall_events.items():
                if event_data["acknowledged"] or event_data["reminder_sent"]:
                    continue

                elapsed = current_time - event_data["created_at"]

                if elapsed >= REMINDER_DELAY_SECONDS:
                    candidates.append((
                        event_key,
                        event_data["household_id"],
                        event_data["event_identifier"],
                        event_data["payload"],
                    ))

        for event_key, household_id, event_identifier, payload in candidates:
            # Website and Telegram both update this same database field.
            acknowledged = get_event_acknowledged(
                household_id,
                event_identifier,
            )

            if acknowledged is True:
                with fall_events_lock:
                    event_data = pending_fall_events.get(event_key)
                    if event_data:
                        event_data["acknowledged"] = True

                print(
                    f"[REMINDER] Event {event_identifier} already "
                    "acknowledged in database; reminder cancelled."
                )
                continue

            # Event may not have been committed to the backend yet.
            if acknowledged is None:
                continue

            with fall_events_lock:
                event_data = pending_fall_events.get(event_key)

                if (
                    event_data is None
                    or event_data["acknowledged"]
                    or event_data["reminder_sent"]
                ):
                    continue

                event_data["reminder_sent"] = True

            camera = payload.get("camera", "Unknown")
            timestamp = payload.get("timestamp", "Unknown")

            reminder_caption = (
                "⚠️ NHẮC LẠI CẢNH BÁO TÉ NGÃ!\n\n"
                "Hệ thống vẫn chưa nhận được xác nhận tiếp nhận "
                "từ người nhà.\n\n"
                f"📷 Camera: {camera}\n"
                f"🕒 Thời gian phát hiện: {timestamp}\n\n"
                "Vui lòng kiểm tra và hỗ trợ người được giám sát!\n\n"
                "Nếu đã tiếp nhận, vui lòng nhấn nút bên dưới."
            )

            print(
                f"[REMINDER] Sending reminder for event "
                f"{event_identifier} to household {household_id}."
            )

            send_telegram_photo(
                payload.get("snapshot_path"),
                reminder_caption,
                event_identifier,
                household_id,
            )

        time.sleep(1)

    print("[REMINDER] Reminder worker stopped.")


# --------------------------------------------------
# MQTT callbacks
# --------------------------------------------------

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[MQTT] Connected successfully.")
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[MQTT] Subscribed to: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Connection failed. Code: {reason_code}")
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))

        if payload.get("event") != "FALL_DETECTED":
            return

        event_identifier = payload.get("event_id") or payload.get("timestamp")

        if not event_identifier:
            print("[WARNING] Event has no unique identifier. Ignoring.")
            return

        event_identifier = str(event_identifier)
        device_id = payload.get("device_id")

        # Resolve household from the registered camera in PostgreSQL.
        household_id = get_household_id_for_device(device_id)

        if household_id is None:
            print(
                f"[MQTT] No registered camera found for device "
                f"{device_id!r}; event ignored."
            )
            return

        if not TELEGRAM_BOT_TOKEN:
            print(
                "[TELEGRAM] Shared Bot Token is missing; "
                "event will not be sent."
            )
            return

        event_key = (
            str(device_id),
            "FALL_DETECTED",
            str(event_identifier),
        )

        if event_key in processed_event_keys:
            print("[DUPLICATE] Event already processed. Ignoring.")
            return

        processed_event_keys.add(event_key)
        processed_event_order.append(event_key)

        household_event_key = (household_id, event_identifier)

        with fall_events_lock:
            pending_fall_events[household_event_key] = {
                "household_id": household_id,
                "event_identifier": event_identifier,
                "created_at": time.monotonic(),
                "acknowledged": False,
                "acknowledged_by": None,
                "reminder_sent": False,
                "payload": payload,
            }

        print(
            f"[REMINDER] Event {event_identifier} registered for "
            f"household {household_id}; waiting "
            f"{REMINDER_DELAY_SECONDS} seconds for acknowledgment."
        )

        if len(processed_event_order) > MAX_PROCESSED_EVENTS:
            oldest_event = processed_event_order.popleft()
            processed_event_keys.discard(oldest_event)

        camera = payload.get("camera", "Unknown")
        timestamp = payload.get("timestamp", "Unknown")

        caption = (
            "🚨 CẢNH BÁO PHÁT HIỆN TÉ NGÃ!\n\n"
            "Hệ thống phát hiện một người có dấu hiệu té ngã.\n\n"
            f"📷 Camera: {camera}\n"
            f"🕒 Thời gian: {timestamp}\n\n"
            "⚠️ Vui lòng kiểm tra và hỗ trợ người được giám sát!"
        )

        print(
            f"[ALERT] Fall detected: {event_identifier}. "
            f"Sending to household {household_id}."
        )

        send_telegram_photo(
            payload.get("snapshot_path"),
            caption,
            event_identifier,
            household_id,
        )

    except Exception as error:
        print(f"[MQTT MESSAGE ERROR] {error}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"[MQTT] Disconnected. Reason code: {reason_code}")

    if reason_code != 0:
        print("[MQTT] Unexpected disconnection. Waiting for automatic reconnect...")

# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    global telegram_polling

    # Validate the shared Bot Token before starting MQTT or worker threads.
    bot_info = get_shared_telegram_bot()
    bot_username = bot_info.get("username", "unknown")

    telegram_polling = True

    print("[DEBUG] RUNNING FILE:", Path(__file__).resolve())
    print("[DEBUG] REMINDER DELAY:", REMINDER_DELAY_SECONDS)
    print("=" * 55)
    print("TELEGRAM FALL ALERT LISTENER - SHARED BOT")
    print("=" * 55)
    print(f"Telegram Bot: @{bot_username}")
    print(f"MQTT Broker: {MQTT_BROKER}")
    print(f"MQTT Topic: {MQTT_TOPIC}")
    print("=" * 55)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    polling_thread = threading.Thread(
        target=poll_shared_bot,
        args=(TELEGRAM_BOT_TOKEN, bot_username),
        daemon=True,
    )

    reminder_thread = threading.Thread(
        target=reminder_worker,
        daemon=True,
    )

    polling_thread.start()
    reminder_thread.start()

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()

    except KeyboardInterrupt:
        print("\n[INFO] Stopping Telegram listener...")

    except Exception as error:
        print(f"[ERROR] Listener: {error}")

    finally:
        telegram_polling = False

        try:
            client.disconnect()
        except Exception:
            pass

        polling_thread.join(timeout=3)
        reminder_thread.join(timeout=3)

        print("[INFO] Listener stopped.")


if __name__ == "__main__":
    main()
