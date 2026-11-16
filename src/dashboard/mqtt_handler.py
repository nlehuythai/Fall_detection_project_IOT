import json
import os
import threading
from pathlib import Path
from copy import deepcopy

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


# =====================================================
# CONFIGURATION
# =====================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "esp32/camera/detection")

MQTT_CLIENT_ID = "Dashboard_Receiver"

HISTORY_FILE = ROOT_DIR / "data" / "fall_history.json"
MAX_HISTORY = 100


# =====================================================
# MQTT HANDLER
# =====================================================

class MQTTListener:

    def __init__(self):
        self.client = None

        self.connected = False
        self.latest_message = None
        self.history = []

        self.lock = threading.Lock()

        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.load_history()

    # -------------------------------------------------
    # LOAD HISTORY
    # -------------------------------------------------

    def load_history(self):
        try:
            if HISTORY_FILE.exists():
                content = HISTORY_FILE.read_text(encoding="utf-8").strip()

                if content:
                    self.history = json.loads(content)

        except (json.JSONDecodeError, OSError) as e:
            print(f"[HISTORY] Load error: {e}")
            self.history = []

    # -------------------------------------------------
    # SAVE HISTORY
    # -------------------------------------------------

    def save_history(self):
        try:
            with self.lock:
                data = json.dumps(
                    self.history,
                    ensure_ascii=False,
                    indent=4
                )

            HISTORY_FILE.write_text(data, encoding="utf-8")

        except OSError as e:
            print(f"[HISTORY] Save error: {e}")

    # -------------------------------------------------
    # MQTT CONNECT CALLBACK
    # -------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):

        if rc == 0:
            self.connected = True

            print("[MQTT] Connected to broker")

            client.subscribe(MQTT_TOPIC, qos=1)

            print(f"[MQTT] Subscribed: {MQTT_TOPIC}")

        else:
            self.connected = False
            print(f"[MQTT] Connection failed: {rc}")

    # -------------------------------------------------
    # MQTT DISCONNECT CALLBACK
    # -------------------------------------------------

    def on_disconnect(self, client, userdata, rc):

        self.connected = False

        print(f"[MQTT] Disconnected: {rc}")

    # -------------------------------------------------
    # MQTT MESSAGE CALLBACK
    # -------------------------------------------------

    def on_message(self, client, userdata, msg):

        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)

            if not isinstance(data, dict):
                print("[MQTT] Invalid JSON structure")
                return

            print("[MQTT] Received event:", data.get("event"))

            with self.lock:
                self.latest_message = data

                self.history.append(data)

                self.history = self.history[-MAX_HISTORY:]

            self.save_history()

        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"[MQTT] Message parsing error: {e}")

    # -------------------------------------------------
    # START MQTT
    # -------------------------------------------------

    def start(self):

        if self.client is not None:
            return self.connected

        try:
            self.client = mqtt.Client(
                client_id=MQTT_CLIENT_ID
            )

            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message

            self.client.connect(
                MQTT_BROKER,
                MQTT_PORT,
                keepalive=60
            )

            self.client.loop_start()

            print("[MQTT] Listener started")

            return True

        except Exception as e:
            self.connected = False
            print(f"[MQTT] Start error: {e}")
            return False

    # -------------------------------------------------
    # GET LATEST MESSAGE
    # -------------------------------------------------

    def get_latest(self):

        with self.lock:
            return deepcopy(self.latest_message)

    # -------------------------------------------------
    # GET HISTORY
    # -------------------------------------------------

    def get_history(self):

        with self.lock:
            return deepcopy(self.history)
    def clear_history(self):

        with self.lock:
            self.history = []
            self.latest_message = None

        self.save_history()

        print("[HISTORY] History cleared successfully")
    # -------------------------------------------------
    # GET CONNECTION STATUS
    # -------------------------------------------------

    def is_connected(self):
        return self.connected

    # -------------------------------------------------
    # STOP MQTT
    # -------------------------------------------------

    def stop(self):

        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()

            self.client = None
            self.connected = False

            print("[MQTT] Listener stopped")