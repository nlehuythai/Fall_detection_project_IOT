import os
from dotenv import load_dotenv
load_dotenv()
import time
import threading
import requests
import paho.mqtt.client as mqtt
from datetime import datetime

# ================= CONFIGURATION =================
# MQTT Settings
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
TOPIC_MPU_FALL = "esp32/mpu6050/fall"
TOPIC_CAMERA   = "esp32/camera/alert"

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PASTE_YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PASTE_YOUR_TELEGRAM_CHAT_ID")

# Logic Settings
VERIFICATION_WINDOW = 3  # seconds
# =================================================

# Global State tracking
last_mpu_fall_time = None
last_camera_time = None

def send_telegram_alert(event_ts):
    """Sends a formatted alert to Telegram with action buttons."""
    event_time_str = datetime.fromtimestamp(event_ts).strftime("%Y-%m-%d %H:%M:%S")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": (
            "🚨 **FALL DETECTED**\n"
            "The system has verified a fall via MPU and Camera sensors.\n\n"
            f"**Time:** {event_time_str}"
        ),
        "parse_mode": "Markdown",
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
            print("✓ Telegram alert sent successfully!")
        else:
            print(f"✗ Telegram failed. Status: {response.status_code}")
    except Exception as e:
        print(f"✗ Telegram Error: {e}")

def reset_state():
    global last_mpu_fall_time, last_camera_time
    last_mpu_fall_time = None
    last_camera_time = None

def try_confirm_fall():
    global last_mpu_fall_time, last_camera_time

    if last_mpu_fall_time and last_camera_time:
        dt = abs(last_mpu_fall_time - last_camera_time)

        if dt <= VERIFICATION_WINDOW:
            print(f"\n🚨 ALERT: Fall Confirmed! (Matched in {dt:.2f}s)")
            # Trigger the Telegram notification
            send_telegram_alert(time.time())
        else:
            print(f"⚠️ Triggers too far apart ({dt:.2f}s) — ignoring event")

        reset_state()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT Broker: {MQTT_BROKER}")
        client.subscribe([(TOPIC_MPU_FALL, 0), (TOPIC_CAMERA, 0)])
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    global last_mpu_fall_time, last_camera_time
    
    payload = msg.payload.decode()
    topic = msg.topic

    # -------- MPU FALL EVENT --------
    if topic == TOPIC_MPU_FALL:
        print("⚠️ [MPU] Fall trigger received!")
        last_mpu_fall_time = time.time()
        try_confirm_fall()

    # -------- CAMERA ALERT --------
    elif topic == TOPIC_CAMERA:
        # Check if the camera payload contains the alert keyword
        if "🚨 ALERT: Fall confirmed" in payload:
            print("⚠️ [Camera] Vision system confirms fall!")
            last_camera_time = time.time()
            try_confirm_fall()

# ================= MAIN EXECUTION =================

if __name__ == '__main__':
    print("--- Fall Monitor System (Sync + Telegram Mode) ---")
    print("Listening for sensor data...")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        # Run MQTT loop in a background thread
        mqtt_thread = threading.Thread(target=client.loop_forever, daemon=True)
        mqtt_thread.start()

        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping system...")
