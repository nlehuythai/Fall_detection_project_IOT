import os
from dotenv import load_dotenv
load_dotenv()
import requests
from datetime import datetime 
import time

# Your configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PASTE_YOUR_TELEGRAM_CHAT_ID")

def send_test_message(event_ts=None):
    if event_ts is None:
        event_ts = time.time()

    event_time_str = datetime.fromtimestamp(event_ts).strftime("%Y-%m-%d %H:%M :%S")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": (
            "🚨 FALL DETECTED\n"
            f"Time: {event_time_str}"
        ),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✅ Acknowledged", "callback_data": "ack"},
                    {"text": "🚑 Call Help", "callback_data": "help"}
                ]
            ]
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✓ Test message sent successfully!")
            print("Telegram Response:", response.json())
        else:
            print(f"✗ Failed to send message. Status code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✓ Test message sent successfully!")
            print("Telegram Response : response.json() =", response.json())
        else:
            print(f"✗ Failed to send message. Status code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == '__main__':
    send_test_message()
