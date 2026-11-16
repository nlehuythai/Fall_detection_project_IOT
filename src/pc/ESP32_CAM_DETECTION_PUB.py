
import os
import json
import time
from pathlib import Path
from collections import deque
from datetime import datetime, timezone
import cv2
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from ultralytics import YOLO
import uuid
import requests

# ============================================================
# PROJECT CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
SNAPSHOT_DIR = ROOT_DIR / "data" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# BACKEND API
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

DEVICE_ID = os.getenv("DEVICE_ID")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY")

BACKEND_EVENT_URL = f"{BACKEND_API_URL}/households/devices/events"
# MQTT
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/camera/detection"
MQTT_CLIENT_ID = "Camera_Publisher"

# MODEL
DEFAULT_MODEL = (
    ROOT_DIR
    / "training"
    / "results"
    / "fall_detection_yolo11n_v1"
    / "weights"
    / "best.pt"
)

MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL)))

if not MODEL_PATH.is_absolute():
    MODEL_PATH = ROOT_DIR / MODEL_PATH

# CAMERA
# ===========================
# CAMERA CONFIGURATION
# ===========================

CAMERA_TYPE = "webcam"  # "webcam" hoặc "esp32"

WEBCAM_SOURCE =int(os.getenv("WEBCAM_SOURCE", "0"))  # 0 cho webcam mặc định, hoặc đường dẫn RTSP/HTTP cho webcam IP
ESP32_CAMERA_URL = os.getenv("ESP32_CAMERA_URL")

if CAMERA_TYPE == "webcam":
    CAMERA_SOURCE = WEBCAM_SOURCE
elif CAMERA_TYPE == "esp32":
    CAMERA_SOURCE = ESP32_CAMERA_URL
else:
    raise ValueError(f"Unsupported camera type: {CAMERA_TYPE}")

# DETECTION
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.5"))
IMAGE_SIZE = 640

# ALERT
FALL_COOLDOWN_SECONDS = 5
# Fall confirmation
FALL_CONFIRM_SECONDS = 1.5
FALL_MISSING_GRACE_SECONDS = 0.5
FALL_MIN_AVG_CONFIDENCE = 0.60
# MQTT retry
ALERT_RETRY_INTERVAL = 2.0
CLASS_NAMES = {
    0: "Fallen",
    1: "Non-fallen"
}

mqtt_client = None

last_alert_time = 0.0
last_publish_attempt = 0.0

fallen_start_time = None
fallen_last_seen_time = None

fallen_confidences = deque(maxlen=30)

fall_confirmed = False
fall_alert_sent = False
fall_event_id = None
fall_snapshot_path = None
fall_occurred_at = None
# BACKEND STATE
backend_event_sent = False
last_backend_attempt = 0.0
BACKEND_RETRY_INTERVAL = 5.0
# ============================================================
# MQTT
# ============================================================

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected successfully")
        print(f"[MQTT] Topic: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Connection failed: {rc}")


def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[MQTT] Unexpected disconnection: {rc}")


def setup_mqtt():
    global mqtt_client

    try:
        mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)

        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect

        print(
            f"[MQTT] Connecting to "
            f"{MQTT_BROKER}:{MQTT_PORT}..."
        )

        mqtt_client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            60
        )

        mqtt_client.loop_start()

        return mqtt_client

    except Exception as e:
        print(f"[MQTT] Connection error: {e}")
        return None

def save_fall_snapshot(frame, event_id):
    if frame is None:
        print("[SNAPSHOT] Empty frame. Cannot save image.")
        return None

    try:
        now = datetime.now()

        # Tạo thư mục theo năm/tháng/ngày
        date_folder = (
            SNAPSHOT_DIR
            / str(now.year)
            / f"{now.month:02d}"
            / f"{now.day:02d}"
        )

        date_folder.mkdir(parents=True, exist_ok=True)

        # Tên ảnh theo event_id
        filename = f"{event_id}.jpg"
        image_path = date_folder / filename

        height, width = frame.shape[:2]

        if width > 1280:
            new_height = int(height * 1280 / width)

            snapshot_frame = cv2.resize(
                frame,
                (1280, new_height),
                interpolation=cv2.INTER_AREA
            )
        else:
            snapshot_frame = frame

        # Lưu ảnh JPEG với chất lượng 80
        success = cv2.imwrite(
            str(image_path),
            snapshot_frame,
            [cv2.IMWRITE_JPEG_QUALITY, 80]
        )

        if success:
            file_size_kb = image_path.stat().st_size / 1024
            print(f"[SNAPSHOT] Image size: {file_size_kb:.2f} KB")
        if not success:
            print("[SNAPSHOT] Failed to save image.")
            return None

        print(f"[SNAPSHOT] Saved: {image_path}")

        return image_path

    except Exception as error:
        print(f"[SNAPSHOT ERROR] {error}")
        return None
def publish_detection(
    detections,
    average_confidence,
    elapsed_time,
    event_id=None,
    snapshot_path=None
):
    if not detections:
        return False

    if mqtt_client is None or not mqtt_client.is_connected():
        print("[MQTT] Not connected. Alert not sent.")
        return False

    try:
        payload_data = {
            "device_id": "CAMERA_01",
            "event": "FALL_DETECTED",
            "camera": (
                "Laptop Webcam"
                if CAMERA_TYPE=="webcam"
                else "ESP32-CAM"
            ),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds"),
            "fall_duration_seconds": round(elapsed_time, 2),
            "average_confidence": round(average_confidence, 3),
            "detections": detections,
            "event_id": event_id,
            "snapshot_path": str(snapshot_path) if snapshot_path else None,
        }

        payload = json.dumps(payload_data)

        result = mqtt_client.publish(
            MQTT_TOPIC,
            payload,
            qos=1
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("[MQTT] FALL ALERT published")
            return True

        print(f"[MQTT] Publish failed: {result.rc}")
        return False

    except Exception as e:
        print(f"[MQTT] Publish error: {e}")
        return False
def send_event_to_backend(event_id, occurred_at, elapsed_time, average_confidence, snapshot_path=None):
    if not DEVICE_ID or not DEVICE_API_KEY:
        print("[BACKEND] DEVICE_ID or DEVICE_API_KEY is not configured.")
        return False
    snapshot_key = None

    if snapshot_path:
        try:
            snapshot_key = snapshot_path.relative_to(
                SNAPSHOT_DIR
            ).as_posix()
        except ValueError:
            print("[SNAPSHOT] Cannot create relative snapshot path.")
    payload = {
        "event_id": event_id,
        "occurred_at": occurred_at.isoformat(timespec="seconds"),
        "fall_duration_seconds": round(elapsed_time, 2),
        "average_confidence": round(average_confidence, 3),
        "snapshot_key": snapshot_key
    }

    headers = {
        "X-Device-ID": DEVICE_ID,
        "X-Device-Key": DEVICE_API_KEY
    }

    try:
        response = requests.post(
            BACKEND_EVENT_URL,
            json=payload,
            headers=headers,
            timeout=5
        )

        if response.status_code == 201:
            print("[BACKEND] Fall event saved successfully.")
            return True

        if response.status_code == 409:
            print("[BACKEND] Event already exists.")
            return True

        print(
            f"[BACKEND] Submission failed: "
            f"HTTP {response.status_code} - {response.text}"
        )
        return False

    except requests.RequestException as error:
        print(f"[BACKEND] Request error: {error}")
        return False
# ============================================================
# MODEL
# ============================================================

def load_model():
    print(f"[MODEL] Loading: {MODEL_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    model = YOLO(str(MODEL_PATH))

    print("[MODEL] Loaded successfully")
    print(f"[MODEL] Classes: {model.names}")

    # Verify class mapping
    names = model.names

    for class_id, expected_name in CLASS_NAMES.items():
        actual_name = names.get(class_id)

        if actual_name != expected_name:
            raise ValueError(
                f"Incorrect class mapping! "
                f"Expected {class_id}: {expected_name}, "
                f"got {actual_name}"
            )

    print("[MODEL] Class mapping verified")

    return model


# ============================================================
# CAMERA
# ============================================================
def open_camera():
    if isinstance(CAMERA_SOURCE, int):
        cap = cv2.VideoCapture(
            CAMERA_SOURCE,
            cv2.CAP_DSHOW
        )

        camera_name = f"Laptop Webcam ({CAMERA_SOURCE})"

    elif isinstance(CAMERA_SOURCE, str):
        cap = cv2.VideoCapture(CAMERA_SOURCE)
        if cap.isOpened():
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

            print(f"[CAMERA] Resolution: {int(width)}x{int(height)}")
        camera_name = f"ESP32-S3 Camera ({CAMERA_SOURCE})"

        # Giảm số frame tồn đọng trong buffer nếu backend hỗ trợ
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    else:
        raise ValueError(
            f"Invalid CAMERA_SOURCE: {CAMERA_SOURCE}"
        )

    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera: {camera_name}"
        )

    print(f"[CAMERA] Opened: {camera_name}")

    return cap

# ============================================================
# OBJECT DETECTION
# ============================================================


def object_detection(model, frame):
    global last_alert_time
    global fallen_start_time
    global fall_alert_sent
    global fall_event_id
    global fall_snapshot_path
    global backend_event_sent
    global last_backend_attempt
    global fall_occurred_at
    results = model.predict(
        source=frame,
        imgsz=IMAGE_SIZE,
        conf=CONF_THRESHOLD,
        verbose=False
    )

    result = results[0]
    annotated_frame = result.plot()

    detections = []
    fallen_detections = []

    image_height, image_width = frame.shape[:2]

    if result.boxes is not None:
        for box in result.boxes:

            class_id = int(box.cls[0].item())
            class_name = result.names[class_id]
            confidence = float(box.conf[0].item())

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            box_width = x2 - x1
            box_height = y2 - y1

            detection = {
                "Object type": class_name,
                "Class ID": class_id,
                "Coordinates": [
                    round(x1),
                    round(y1),
                    round(x2),
                    round(y2)
                ],
                "Probability": round(confidence, 3),
                "X Center": round(
                    (x1 + box_width / 2) / image_width,
                    3
                ),
                "Y Center": round(
                    (y1 + box_height / 2) / image_height,
                    3
                ),
                "Width": round(box_width / image_width, 3),
                "Height": round(box_height / image_height, 3)
            }

            detections.append(detection)

            if class_id == 0:
                fallen_detections.append(detection)

    current_time = time.monotonic()

    global fallen_last_seen_time
    global fallen_confidences
    global fall_confirmed
    global last_publish_attempt

    # ========================================================
    # TEMPORAL FALL CONFIRMATION
    # ========================================================

    if fallen_detections:

        # Start a new fall event only once
        if fallen_start_time is None:

            fallen_start_time = current_time
            fallen_last_seen_time = current_time

            fallen_confidences.clear()

            fall_confirmed = False
            fall_alert_sent = False

            print("[ALERT] Fallen detected - monitoring...")

        # Update last detection time
        fallen_last_seen_time = current_time

        # Store highest Fallen confidence
        current_confidence = max(
            det["Probability"]
            for det in fallen_detections
        )

        fallen_confidences.append(current_confidence)

    else:

        # Reset only after Fallen disappears long enough
        if (
            fallen_start_time is not None
            and fallen_last_seen_time is not None
            and current_time - fallen_last_seen_time
            > FALL_MISSING_GRACE_SECONDS
        ):

            print("[ALERT] Fall event ended - resetting state")

            fallen_start_time = None
            fallen_last_seen_time = None

            fallen_confidences.clear()

            fall_confirmed = False
            fall_alert_sent = False
            fall_event_id = None
            fall_snapshot_path = None
            backend_event_sent = False
            last_backend_attempt = 0.0
    # ========================================================
    # CHECK FALL CONFIRMATION
    # ========================================================

    if (
        fallen_start_time is not None
        and fallen_last_seen_time is not None
        and current_time - fallen_last_seen_time
        <= FALL_MISSING_GRACE_SECONDS
    ):

        elapsed_time = current_time - fallen_start_time

        if fallen_confidences:

            average_confidence = sum(fallen_confidences) / len(
                fallen_confidences
            )

            print(
                f"[ALERT] Monitoring: "
                f"{elapsed_time:.2f}/{FALL_CONFIRM_SECONDS:.2f}s | "
                f"Average confidence: {average_confidence:.3f}"
            )

            # Confirm fall only once
            # Debug confirmation conditions
            if elapsed_time >= FALL_CONFIRM_SECONDS:
                print(
                    f"[DEBUG] elapsed={elapsed_time:.2f} | "
                    f"avg_conf={average_confidence:.3f} | "
                    f"threshold={FALL_MIN_AVG_CONFIDENCE:.2f} | "
                    f"confirmed={fall_confirmed}"
                )

            # Confirm fall only once
            if (
                elapsed_time >= FALL_CONFIRM_SECONDS
                and average_confidence >= FALL_MIN_AVG_CONFIDENCE
                and not fall_confirmed
            ):

                fall_confirmed = True

                print("[ALERT] FALL CONFIRMED!")

                fall_event_id = (
                    f"FALL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                    f"{uuid.uuid4().hex[:8]}"
                    )
                fall_occurred_at = datetime.now(timezone.utc)
                    # Save original camera frame
                fall_snapshot_path = save_fall_snapshot(
                    frame,
                    fall_event_id
                    )
            # ====================================================
            # SEND MQTT ALERT
            # ====================================================

    if fall_confirmed and not fall_alert_sent:

        cooldown_ok = (
            current_time - last_alert_time
            >= FALL_COOLDOWN_SECONDS
        )

        retry_ok = (
            current_time - last_publish_attempt
            >= ALERT_RETRY_INTERVAL
        )

        if cooldown_ok and retry_ok:

            last_publish_attempt = current_time

            if publish_detection(
                fallen_detections,
                average_confidence,
                elapsed_time,
                fall_event_id,
                fall_snapshot_path
            ):

                last_alert_time = current_time
                fall_alert_sent = True

                print("[ALERT] MQTT notification accepted")

            else:
                print("[ALERT] MQTT failed - will retry")


# ============================================================
# SEND FALL EVENT TO BACKEND
# ============================================================

    if fall_confirmed and not backend_event_sent:

        if current_time - last_backend_attempt >= BACKEND_RETRY_INTERVAL:

            last_backend_attempt = current_time

            if send_event_to_backend(
                fall_event_id,
                fall_occurred_at,
                elapsed_time,
                average_confidence,
                snapshot_path=fall_snapshot_path
            ):
                backend_event_sent = True
                print("[BACKEND] Event synchronized successfully.")

            else:
                print("[BACKEND] Failed - will retry.")

    return annotated_frame, detections, fallen_detections
# ============================================================
# MAIN
# ============================================================

def main():
    global mqtt_client

    print("\n" + "=" * 60)
    print("FALL DETECTION SYSTEM")
    print("=" * 60)

    cap = None

    try:
        # Load model
        model = load_model()

        # Connect MQTT
        mqtt_client = setup_mqtt()

        if mqtt_client is None:
            print("[WARNING] MQTT unavailable")

        # Open camera
        cap = open_camera()

        print("\n[SYSTEM] Ready")
        print("[SYSTEM] Class 0: Fallen")
        print("[SYSTEM] Class 1: Non-fallen")
        print(f"[SYSTEM] Confidence: {CONF_THRESHOLD}")
        print(f"[SYSTEM] Cooldown: {FALL_COOLDOWN_SECONDS}s")
        print(f"[SYSTEM] Fall confirmation: {FALL_CONFIRM_SECONDS}s")
        print("[SYSTEM] Press Q to quit\n")

        frame_count = 0

        read_failures = 0
        MAX_READ_FAILURES = 10
        should_exit = False
        cv2.namedWindow(
            "Fall Detection System",
            cv2.WINDOW_NORMAL
        )
        while True:

            success, frame = cap.read()

            if not success:
                read_failures += 1

                print(
                    f"[CAMERA] Failed to read frame "
                    f"({read_failures}/{MAX_READ_FAILURES})"
                )

                if read_failures >= MAX_READ_FAILURES:

                    print("[CAMERA] Connection lost!")

                    # Webcam: dừng chương trình khi mất kết nối
                    if CAMERA_TYPE == "webcam":
                        print("[CAMERA] Webcam unavailable. Stopping...")
                        break

                    # ESP32: tự động reconnect
                    print("[CAMERA] Reconnecting ESP32-S3...")

                    cap.release()
                    cap = None

                    while cap is None:

                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            should_exit = True
                            break

                        try:
                            print("[CAMERA] Trying to reconnect...")

                            time.sleep(3)

                            cap = open_camera()

                            print("[CAMERA] Reconnected successfully!")

                            read_failures = 0

                        except Exception as e:
                            print(f"[CAMERA] Reconnect failed: {e}")
                            time.sleep(5)

                    if should_exit:
                        break

                else:
                    time.sleep(0.2)

                continue

            read_failures = 0

            frame_count += 1

            annotated_frame, detections, fallen = (
                object_detection(model, frame)
            )

            if detections:
                print(f"\n--- Frame {frame_count} ---")

                for det in detections:
                    print(
                        f"[{det['Object type']}] "
                        f"Confidence: {det['Probability']:.3f}"
                    )

            cv2.imshow(
                "Fall Detection System",
                annotated_frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[SYSTEM] User requested exit")
                break

    except KeyboardInterrupt:
        print("\n[SYSTEM] Interrupted")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    finally:
        print("\n[SYSTEM] Cleaning up...")

        if cap is not None:
            cap.release()

        cv2.destroyAllWindows()

        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

        print("[SYSTEM] Stopped")


if __name__ == "__main__":
    main()
