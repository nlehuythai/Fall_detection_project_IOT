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

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# --------------------------------------------------
# Project path and backend imports
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from src.backend.db import SessionLocal
from src.backend.models import (
    Camera,
    FallEvent,
    HouseholdTelegramBot,
    HouseholdTelegramChat,
)
from src.backend.telegram_security import decrypt_telegram_token


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC", "esp32/camera/detection"
)

CLIENT_ID = "Telegram_Alert_Listener"
MAX_PROCESSED_EVENTS = 100
REMINDER_DELAY_SECONDS = 60

telegram_polling = True
fall_events_lock = threading.Lock()

# Keyed by event_id. Each event stores its household_id and MQTT payload.
pending_fall_events = {}
acknowledged_event_ids = set()

processed_event_keys = set()
processed_event_order = deque()

# Filled at startup from household_telegram_bots.
BOT_CONFIGS_BY_HOUSEHOLD = {}


# --------------------------------------------------
# Database helpers
# --------------------------------------------------

def load_household_telegram_bots():
    """Load active household bots and decrypt their tokens in memory."""
    db = SessionLocal()

    try:
        bots = db.query(HouseholdTelegramBot).filter(
            HouseholdTelegramBot.is_active.is_(True)
        ).all()

        bot_configs = []

        for bot in bots:
            try:
                token = decrypt_telegram_token(bot.bot_token_encrypted)
            except Exception as error:
                print(
                    f"[TELEGRAM CONFIG ERROR] Cannot decrypt token "
                    f"for household {bot.household_id}: {error}"
                )
                continue

            if not token or not bot.bot_username:
                print(
                    f"[TELEGRAM CONFIG WARNING] Incomplete bot config "
                    f"for household {bot.household_id}"
                )
                continue

            bot_configs.append({
                "household_id": bot.household_id,
                "bot_username": bot.bot_username,
                "bot_token": token,
            })

        return bot_configs

    finally:
        db.close()


def get_household_chat_ids(household_id):
    """Return only Telegram chats linked to this household."""
    db = SessionLocal()

    try:
        rows = db.query(HouseholdTelegramChat.telegram_chat_id).filter(
            HouseholdTelegramChat.household_id == household_id,
            HouseholdTelegramChat.telegram_chat_id.isnot(None),
            HouseholdTelegramChat.linked_at.isnot(None),
        ).all()

        return list(dict.fromkeys(str(row[0]) for row in rows))

    finally:
        db.close()


def get_household_id_for_device(device_id):
    """Resolve the household from the registered camera, not MQTT input."""
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
    Return None when the event row is not found yet.
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


# --------------------------------------------------
# Telegram linking
# --------------------------------------------------

def link_telegram_chat(household_id, chat_id, link_code):
    db = SessionLocal()

    try:
        link_code_hash = hashlib.sha256(
            link_code.encode("utf-8")
        ).hexdigest()

        telegram_chat = db.query(HouseholdTelegramChat).filter(
            HouseholdTelegramChat.household_id == household_id,
            HouseholdTelegramChat.link_code_hash == link_code_hash,
            HouseholdTelegramChat.link_code_expires_at > datetime.now(timezone.utc),
        ).first()

        if telegram_chat is None:
            return False, "Mã liên kết không hợp lệ hoặc đã hết hạn."

        telegram_chat.telegram_chat_id = int(chat_id)
        telegram_chat.linked_at = datetime.now(timezone.utc)
        telegram_chat.link_code_hash = None
        telegram_chat.link_code_expires_at = None

        db.commit()
        return True, "Liên kết Telegram thành công!"

    except Exception as error:
        db.rollback()
        print(f"[TELEGRAM LINK ERROR] {error}")
        return False, "Không thể liên kết Telegram. Có thể tài khoản này đã được liên kết."

    finally:
        db.close()


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


def handle_telegram_start(message, household_id, bot_token):
    chat = message.get("chat", {})
    sender = message.get("from", {})

    # Only private chats can be linked.
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
        reply = "Vui lòng tạo mã liên kết trên Website, sau đó mở liên kết Telegram từ Website."
    else:
        link_code = parts[1].strip()
        _, reply = link_telegram_chat(
            household_id=household_id,
            chat_id=chat_id,
            link_code=link_code,
        )

    try:
        result = send_telegram_text_to_chat(bot_token, chat_id, reply)
        if not result.get("ok"):
            print("[TELEGRAM LINK] Telegram did not accept the reply.")
    except Exception as error:
        print(f"[TELEGRAM LINK SEND ERROR] {error}")


# --------------------------------------------------
# Telegram send functions
# --------------------------------------------------

def send_telegram_message(message, household_id):
    bot_config = BOT_CONFIGS_BY_HOUSEHOLD.get(household_id)

    if not bot_config:
        print(
            f"[TELEGRAM] No active bot for household {household_id}; "
            "message was not sent."
        )
        return

    chat_ids = get_household_chat_ids(household_id)

    if not chat_ids:
        print(
            f"[TELEGRAM] No linked Telegram recipients "
            f"for household {household_id}."
        )
        return

    bot_token = bot_config["bot_token"]

    for chat_id in chat_ids:
        try:
            result = send_telegram_text_to_chat(
                bot_token,
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
                    f"for household {household_id}."
                )

        except Exception as error:
            print(f"[TELEGRAM SEND ERROR] {error}")


def send_telegram_photo(
    image_path,
    caption,
    event_identifier,
    household_id,
):
    bot_config = BOT_CONFIGS_BY_HOUSEHOLD.get(household_id)

    if not bot_config:
        print(
            f"[TELEGRAM] No active bot for household {household_id}; "
            "photo was not sent."
        )
        return

    chat_ids = get_household_chat_ids(household_id)

    if not chat_ids:
        print(
            f"[TELEGRAM] No linked Telegram recipients "
            f"for household {household_id}."
        )
        return

    bot_token = bot_config["bot_token"]
    image_path = Path(image_path) if image_path else None

    if image_path and not image_path.is_absolute():
        image_path = ROOT_DIR / image_path

    if image_path is None or not image_path.is_file():
        print(f"[SNAPSHOT ERROR] Image not found: {image_path}")
        send_telegram_message(caption, household_id)
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    reply_markup = {
        "inline_keyboard": [[{
            "text": "✅ Đã tiếp nhận cảnh báo",
            "callback_data": f"ACK|{event_identifier}",
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
            add_field("reply_markup", json.dumps(reply_markup, ensure_ascii=False))

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
                    f"for household {household_id}."
                )

        except Exception as error:
            print(f"[TELEGRAM PHOTO ERROR] {error}")


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
# Long polling: one independent polling loop per household bot
# --------------------------------------------------

def poll_household_bot(bot_config):
    household_id = bot_config["household_id"]
    bot_token = bot_config["bot_token"]
    bot_username = bot_config["bot_username"]

    offset = None

    print(
        f"[TELEGRAM] Starting Bot @{bot_username} "
        f"for household {household_id}."
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
                print(
                    f"[TELEGRAM ERROR] getUpdates failed "
                    f"for household {household_id}."
                )
                time.sleep(3)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message")
                if message:
                    handle_telegram_start(
                        message,
                        household_id,
                        bot_token,
                    )
                    continue

                callback = update.get("callback_query")
                if not callback:
                    continue

                callback_data = callback.get("data", "")
                if not callback_data.startswith("ACK|"):
                    continue

                event_identifier = callback_data.split("|", 1)[1]
                callback_message = callback.get("message") or {}
                chat = callback_message.get("chat") or {}
                chat_id = chat.get("id")

                if not chat_id:
                    answer_telegram_callback(
                        callback["id"],
                        "Không xác định được tài khoản Telegram.",
                        bot_token,
                    )
                    continue

                # Check both: this Telegram chat is linked to this household,
                # and the event belongs to this same household.
                db = SessionLocal()
                try:
                    linked_chat = db.query(HouseholdTelegramChat).filter(
                        HouseholdTelegramChat.household_id == household_id,
                        HouseholdTelegramChat.telegram_chat_id == int(chat_id),
                        HouseholdTelegramChat.linked_at.isnot(None),
                    ).first()

                    event = db.query(FallEvent).filter(
                        FallEvent.household_id == household_id,
                        FallEvent.event_id == event_identifier,
                    ).first()

                    if linked_chat is None:
                        ack_success = False
                        ack_reply = "Bạn chưa liên kết Telegram với hộ gia đình này."
                    elif event is None:
                        ack_success = False
                        ack_reply = "Không tìm thấy cảnh báo trong hộ gia đình này."
                    else:
                        event.acknowledged = True
                        db.commit()
                        ack_success = True
                        ack_reply = "Đã ghi nhận! Cảm ơn bạn đã tiếp nhận cảnh báo."

                except Exception as error:
                    db.rollback()
                    print(f"[ACK DATABASE ERROR] {error}")
                    ack_success = False
                    ack_reply = "Không thể cập nhật trạng thái xác nhận."
                finally:
                    db.close()

                if ack_success:
                    with fall_events_lock:
                        event_data = pending_fall_events.get(event_identifier)
                        if event_data:
                            event_data["acknowledged"] = True
                            event_data["acknowledged_by"] = str(chat_id)

                        acknowledged_event_ids.add(event_identifier)

                    print(
                        f"[ACKNOWLEDGED] Event {event_identifier} "
                        f"| Household {household_id} | Chat {chat_id}"
                    )
                    print("[REMINDER] Reminder cancelled for this event.")

                answer_telegram_callback(
                    callback["id"],
                    ack_reply,
                    bot_token,
                )

        except Exception as error:
            if telegram_polling:
                print(
                    f"[TELEGRAM POLLING ERROR] "
                    f"Household {household_id}: {error}"
                )
                time.sleep(3)

    print(
        f"[TELEGRAM] Polling stopped for household {household_id}."
    )


# --------------------------------------------------
# Reminder worker: check PostgreSQL before sending reminder
# --------------------------------------------------

def reminder_worker():
    print("[REMINDER] Reminder worker started.")

    while telegram_polling:
        current_time = time.monotonic()
        candidates = []

        with fall_events_lock:
            for event_identifier, event_data in pending_fall_events.items():
                if event_data["acknowledged"] or event_data["reminder_sent"]:
                    continue

                elapsed = current_time - event_data["created_at"]
                if elapsed >= REMINDER_DELAY_SECONDS:
                    candidates.append((
                        event_identifier,
                        event_data["household_id"],
                        event_data["payload"],
                    ))

        for event_identifier, household_id, payload in candidates:
            # Website and Telegram both update this same database field.
            acknowledged = get_event_acknowledged(
                household_id,
                event_identifier,
            )

            if acknowledged is True:
                with fall_events_lock:
                    event_data = pending_fall_events.get(event_identifier)
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
                event_data = pending_fall_events.get(event_identifier)
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

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected successfully.")
        client.subscribe(MQTT_TOPIC, qos=1)
        print(f"[MQTT] Subscribed to: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Connection failed. Code: {rc}")


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
        household_id = get_household_id_for_device(device_id)

        if household_id is None:
            print(
                f"[MQTT] No registered camera found for device "
                f"{device_id!r}; event ignored."
            )
            return

        if household_id not in BOT_CONFIGS_BY_HOUSEHOLD:
            print(
                f"[TELEGRAM] No active Bot for household {household_id}; "
                "event will not be sent to Telegram."
            )
            return

        event_key = (str(device_id), "FALL_DETECTED", str(event_identifier))

        if event_key in processed_event_keys:
            print("[DUPLICATE] Event already processed. Ignoring.")
            return

        processed_event_keys.add(event_key)
        processed_event_order.append(event_key)

        with fall_events_lock:
            pending_fall_events[event_identifier] = {
                "household_id": household_id,
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


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Disconnected. Code: {rc}")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    global telegram_polling, BOT_CONFIGS_BY_HOUSEHOLD

    telegram_polling = True

    bot_configs = load_household_telegram_bots()
    BOT_CONFIGS_BY_HOUSEHOLD = {
        bot["household_id"]: bot for bot in bot_configs
    }

    print(
        f"[TELEGRAM] Found {len(BOT_CONFIGS_BY_HOUSEHOLD)} "
        "active household Bot(s)."
    )

    for household_id, bot in BOT_CONFIGS_BY_HOUSEHOLD.items():
        chat_ids = get_household_chat_ids(household_id)
        print(
            f"[TELEGRAM] Household {household_id}: "
            f"@{bot['bot_username']} | linked recipients: {len(chat_ids)}"
        )

    print("[DEBUG] RUNNING FILE:", Path(__file__).resolve())
    print("[DEBUG] REMINDER DELAY:", REMINDER_DELAY_SECONDS)
    print("=" * 55)
    print("TELEGRAM FALL ALERT LISTENER")
    print("=" * 55)
    print(f"MQTT Broker: {MQTT_BROKER}")
    print(f"MQTT Topic: {MQTT_TOPIC}")
    print("=" * 55)

    client = mqtt.Client(client_id=CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    polling_threads = []

    for bot_config in bot_configs:
        thread = threading.Thread(
            target=poll_household_bot,
            args=(bot_config,),
            daemon=True,
        )
        thread.start()
        polling_threads.append(thread)

    reminder_thread = threading.Thread(
        target=reminder_worker,
        daemon=True,
    )
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
        client.disconnect()

        for thread in polling_threads:
            thread.join(timeout=2)

        reminder_thread.join(timeout=2)
        print("[INFO] Listener stopped.")


if __name__ == "__main__":
    main()
