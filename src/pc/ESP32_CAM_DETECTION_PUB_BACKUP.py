import math
import numpy as np

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
POSE_MODEL_PATH =(
    ROOT_DIR
    / "training"
    / "results"
    / "fall_detection_yolo11n_v1"
    / "weights"
    / "yolo11n-pose.pt")
KEYPOINT_THRESHOLD = 0.3
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL)))

if not MODEL_PATH.is_absolute():
    MODEL_PATH = ROOT_DIR / MODEL_PATH

# CAMERA
# ============================================================
# POSE KEYPOINT INDEX
# ============================================================

LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6

LEFT_HIP = 11
RIGHT_HIP = 12

REQUIRED_POINTS = [
    LEFT_SHOULDER,
    RIGHT_SHOULDER,
    LEFT_HIP,
    RIGHT_HIP
]


# ============================================================
# POSE FEATURE EXTRACTION
# ============================================================

def calculate_torso_angle(keypoints):
    """
    Tính góc thân người so với phương thẳng đứng.

    0 độ: đứng thẳng
    90 độ: thân nằm ngang
    """

    shoulder = (
        keypoints[LEFT_SHOULDER]
        + keypoints[RIGHT_SHOULDER]
    ) / 2

    hip = (
        keypoints[LEFT_HIP]
        + keypoints[RIGHT_HIP]
    ) / 2

    dx = hip[0] - shoulder[0]
    dy = hip[1] - shoulder[1]

    angle = math.degrees(
        math.atan2(abs(dx), abs(dy))
    )

    return angle, hip


def extract_pose_features(
    result,
    previous_hip_y,
    previous_time
):
    """
    Trích xuất góc thân, vị trí hông và vận tốc hông.
    """

    if result.keypoints is None:
        return None

    if len(result.keypoints) == 0:
        return None

    keypoints = result.keypoints.xy[0].cpu().numpy()
    keypoint_conf = result.keypoints.conf[0].cpu().numpy()

    # Kiểm tra độ tin cậy của vai và hông
    if not all(
        keypoint_conf[i] > KEYPOINT_THRESHOLD
        for i in REQUIRED_POINTS
    ):
        return None

    angle, hip = calculate_torso_angle(keypoints)

    current_time = time.time()
    current_hip_y = float(hip[1])

    # Tính vận tốc hông theo trục dọc
    hip_velocity = 0.0

    if previous_hip_y is not None and previous_time is not None:

        delta_time = current_time - previous_time

        if delta_time > 0:
            hip_velocity = (
                current_hip_y - previous_hip_y
            ) / delta_time

    average_confidence = float(
        np.mean([
            keypoint_conf[i]
            for i in REQUIRED_POINTS
        ])
    )

    return {
        "torso_angle": float(angle),
        "hip_x": float(hip[0]),
        "hip_y": current_hip_y,
        "hip_velocity": float(hip_velocity),
        "keypoint_confidence": average_confidence,
        "keypoints": keypoints,
        "keypoint_scores": keypoint_conf,
        "timestamp": current_time
    }
# ============================================================
# TEMPORAL FALL ANALYSIS
# ============================================================

class FallTemporalAnalyzer:

    def __init__(self):
        self.history = deque(maxlen=40)
        self.detection_history = deque(maxlen=15)

        self.state = "NORMAL"

        self.transition_time = None
        self.low_posture_start = None
        self.recovery_start = None

        self.transition_peak_velocity = 0.0

    def reset_transition(self):
        self.transition_time = None
        self.low_posture_start = None
        self.transition_peak_velocity = 0.0

    def update(self, detection_class, detection_confidence, features):
        current_time = time.time()

        is_fallen = (
            detection_class == "Fallen"
            and detection_confidence >= CONF_THRESHOLD
        )

        self.detection_history.append(is_fallen)

        fallen_ratio = (
            sum(self.detection_history) / len(self.detection_history)
            if self.detection_history else 0.0
        )

        if features is None:
            return {
                "state": self.state,
                "fallen_ratio": fallen_ratio,
                "average_velocity": 0.0,
                "low_duration": 0.0,
                "reason": "Pose unavailable"
            }

        torso_angle = features["torso_angle"]
        hip_y = features["hip_y"]
        hip_velocity = features["hip_velocity"]

        self.history.append({
            "time": current_time,
            "angle": torso_angle,
            "hip_y": hip_y,
            "velocity": hip_velocity
        })

        # Chuyển động trong 1 giây gần nhất
        recent_samples = [
            item for item in self.history
            if current_time - item["time"] <= 1.0
        ]

        average_velocity = (
            float(np.mean([
                item["velocity"] for item in recent_samples
            ]))
            if recent_samples else 0.0
        )

        peak_downward_velocity = max(
            [item["velocity"] for item in recent_samples] + [0.0]
        )

        # Xác định tư thế thấp
        low_posture = torso_angle >= 50

        if low_posture:
            if self.low_posture_start is None:
                self.low_posture_start = current_time

            low_duration = current_time - self.low_posture_start

        else:
            self.low_posture_start = None
            low_duration = 0.0

        # Tìm tư thế đứng gần nhất trong 3 giây
        upright_samples = [
            item for item in self.history
            if current_time - item["time"] <= 3.0
            and item["angle"] <= 35
        ]

        transition_detected = False

        if low_posture and upright_samples:
            previous_upright = upright_samples[-1]

            angle_change = (
                torso_angle - previous_upright["angle"]
            )

            hip_drop = hip_y - previous_upright["hip_y"]

            transition_detected = (
                angle_change >= 20
                and hip_drop >= 20
                and peak_downward_velocity >= 220
            )

        # NORMAL
        if self.state == "NORMAL":

            if transition_detected:
                self.state = "FALL_TRANSITION"
                self.transition_time = current_time

                self.transition_peak_velocity = (
                    peak_downward_velocity
                )

        # FALL_TRANSITION
        elif self.state == "FALL_TRANSITION":

            if not low_posture:
                self.state = "NORMAL"
                self.reset_transition()

            else:
                self.transition_peak_velocity = max(
                    self.transition_peak_velocity,
                    peak_downward_velocity
                )

                if low_duration >= 1.0:
                    self.state = "POSTURE_VERIFICATION"

        # POSTURE_VERIFICATION
        elif self.state == "POSTURE_VERIFICATION":

            if not low_posture:
                self.state = "NORMAL"
                self.reset_transition()

            elif self.transition_time is not None:

                transition_duration = (
                    current_time - self.transition_time
                )

                enough_detection_evidence = (
                    fallen_ratio >= 0.8
                )

                enough_motion_evidence = (
                    self.transition_peak_velocity >= 220
                )

                if (
                    transition_duration >= 2.0
                    and low_duration >= 2.0
                    and enough_detection_evidence
                    and enough_motion_evidence
                ):
                    self.state = "FALL_CONFIRMED"

        # FALL_CONFIRMED
        elif self.state == "FALL_CONFIRMED":

            if not low_posture and not is_fallen:

                if self.recovery_start is None:
                    self.recovery_start = current_time

                elif current_time - self.recovery_start >= 3.0:
                    self.state = "RECOVERED"
                    self.recovery_start = None
                    self.reset_transition()

            else:
                self.recovery_start = None

        # RECOVERED
        elif self.state == "RECOVERED":

            self.state = "NORMAL"
            self.history.clear()
            self.detection_history.clear()
            self.reset_transition()

        return {
            "state": self.state,
            "fallen_ratio": fallen_ratio,
            "average_velocity": average_velocity,
            "low_duration": low_duration,
            "reason": "Analyzing"
        }

# ===========================
# CAMERA CONFIGURATION
# ===========================

CAMERA_TYPE ="esp32"  # "webcam" hoặc "esp32"

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
            "device_id": DEVICE_ID,
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

def load_models():
    # ========================================
    # LOAD DETECTION MODEL
    # ========================================
    print(f"[MODEL] Loading Detection: {MODEL_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Detection model not found: {MODEL_PATH}"
        )

    detection_model = YOLO(str(MODEL_PATH))

    print("[MODEL] Detection model loaded")
    print(f"[MODEL] Detection classes: {detection_model.names}")

    # Verify class mapping
    names = detection_model.names

    for class_id, expected_name in CLASS_NAMES.items():
        actual_name = names.get(class_id)

        if actual_name != expected_name:
            raise ValueError(
                f"Incorrect class mapping! "
                f"Expected {class_id}: {expected_name}, "
                f"got {actual_name}"
            )

    print("[MODEL] Detection class mapping verified")

    # ========================================
    # LOAD POSE MODEL
    # ========================================
    print(f"[MODEL] Loading Pose: {POSE_MODEL_PATH}")

    if not POSE_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Pose model not found: {POSE_MODEL_PATH}"
        )

    pose_model = YOLO(str(POSE_MODEL_PATH))

    print("[MODEL] Pose model loaded")
    print("[MODEL] Pose model classes:", pose_model.names)

    print("[MODEL] Both models loaded successfully")

    return detection_model, pose_model

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


def object_detection(detection_model, pose_model, frame, analyzer):
    global last_alert_time
    global fall_alert_sent
    global fall_event_id
    global fall_snapshot_path
    global backend_event_sent
    global last_backend_attempt
    global fall_occurred_at
    global last_publish_attempt
    global fall_confirmed

    current_time = time.monotonic()

    # ========================================================
    # 1. YOLO DETECTION
    # ========================================================

    detection_results = detection_model.predict(
        source=frame,
        imgsz=IMAGE_SIZE,
        conf=CONF_THRESHOLD,
        verbose=False
    )

    detection_result = detection_results[0]

    detections = []
    fallen_detections = []

    detection_class = "Non-fallen"
    detection_confidence = 0.0

    image_height, image_width = frame.shape[:2]

    if detection_result.boxes is not None:
        for box in detection_result.boxes:

            class_id = int(box.cls[0].item())
            class_name = detection_result.names[class_id]
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
                    (x1 + box_width / 2) / image_width, 3
                ),
                "Y Center": round(
                    (y1 + box_height / 2) / image_height, 3
                ),
                "Width": round(box_width / image_width, 3),
                "Height": round(box_height / image_height, 3)
            }

            detections.append(detection)

            if class_id == 0:
                fallen_detections.append(detection)

            # Select detection with highest confidence
            if confidence > detection_confidence:
                detection_confidence = confidence
                detection_class = CLASS_NAMES[class_id]

    # Cache the latest Fallen detection for alert publishing
    if not hasattr(analyzer, "confidence_history"):
        analyzer.confidence_history = deque(maxlen=15)
        analyzer.last_fallen_detection = None

    if detection_class == "Fallen":
        analyzer.confidence_history.append(detection_confidence)

    if fallen_detections:
        analyzer.last_fallen_detection = max(
            fallen_detections,
            key=lambda item: item["Probability"]
        )

    # ========================================================
    # 2. YOLO POSE
    # ========================================================

    pose_results = pose_model.predict(
        source=frame,
        imgsz=IMAGE_SIZE,
        conf=CONF_THRESHOLD,
        verbose=False
    )

    pose_result = pose_results[0]

    pose_features = extract_pose_features(
        pose_result,
        getattr(analyzer, "previous_hip_y", None),
        getattr(analyzer, "previous_time", None)
    )

    if pose_features is not None:
        analyzer.previous_hip_y = pose_features["hip_y"]
        analyzer.previous_time = pose_features["timestamp"]

    # ========================================================
    # 3. TEMPORAL ANALYSIS
    # ========================================================

    analysis = analyzer.update(
        detection_class,
        detection_confidence,
        pose_features
    )

    state = analysis["state"]

    # ========================================================
    # 4. DISPLAY
    # ========================================================

    annotated_frame = pose_result.plot()

    if state == "FALL_CONFIRMED":
        state_color = (0, 0, 255)
    elif state in ("FALL_TRANSITION", "POSTURE_VERIFICATION"):
        state_color = (0, 165, 255)
    else:
        state_color = (0, 255, 0)

    # Draw Detection boxes
    for detection in detections:
        x1, y1, x2, y2 = detection["Coordinates"]

        color = (
            (0, 0, 255)
            if detection["Class ID"] == 0
            else (0, 255, 0)
        )

        cv2.rectangle(
            annotated_frame,
            (x1, y1),
            (x2, y2),
            color,
            2
        )

        cv2.putText(
            annotated_frame,
            f'{detection["Object type"]} '
            f'({detection["Probability"]:.2f})',
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2
        )

    display_lines = [
        (
            f"Detection: {detection_class} "
            f"({detection_confidence:.2f})",
            (255, 255, 0)
        ),
        (f"State: {state}", state_color),
        (
            f"Fallen ratio: {analysis['fallen_ratio']:.2f}",
            (255, 255, 255)
        ),
        (
            f"Torso angle: "
            f"{pose_features['torso_angle']:.1f}"
            if pose_features is not None
            else "Torso angle: unavailable",
            (255, 255, 255)
        ),
        (
            f"Hip velocity: "
            f"{analysis['average_velocity']:.1f} px/s",
            (255, 255, 255)
        ),
        (
            f"Low duration: {analysis['low_duration']:.1f}s",
            (255, 255, 255)
        )
    ]

    for index, (line, color) in enumerate(display_lines):
        cv2.putText(
            annotated_frame,
            line,
            (15, 30 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    # ========================================================
    # 5. FALL CONFIRMATION
    # ========================================================

    if state == "FALL_CONFIRMED" and not fall_confirmed:

        fall_confirmed = True

        print("[ALERT] FALL CONFIRMED!")

        fall_event_id = (
            f"FALL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}"
        )

        fall_occurred_at = datetime.now(timezone.utc)

        fall_snapshot_path = save_fall_snapshot(
            frame,
            fall_event_id
        )

        fall_alert_sent = False
        backend_event_sent = False
        last_backend_attempt = 0.0

    # Calculate average Fallen confidence
    average_confidence = (
        sum(analyzer.confidence_history)
        / len(analyzer.confidence_history)
        if analyzer.confidence_history
        else detection_confidence
    )

    elapsed_time = analysis["low_duration"]

    # ========================================================
    # 6. SEND MQTT ALERT
    # ========================================================

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

            cached_detection = analyzer.last_fallen_detection

            if cached_detection is not None:
                if publish_detection(
                    [cached_detection],
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

    # ========================================================
    # 7. SEND FALL EVENT TO BACKEND
    # ========================================================

    if fall_confirmed and not backend_event_sent:

        if (
            current_time - last_backend_attempt
            >= BACKEND_RETRY_INTERVAL
        ):

            last_backend_attempt = current_time

            if send_event_to_backend(
                fall_event_id,
                fall_occurred_at,
                elapsed_time,
                average_confidence,
                snapshot_path=fall_snapshot_path
            ):
                backend_event_sent = True

                print(
                    "[BACKEND] Event synchronized successfully."
                )

            else:
                print("[BACKEND] Failed - will retry.")

    # ========================================================
    # 8. RESET AFTER RECOVERY
    # ========================================================

    if state == "RECOVERED":

        print("[ALERT] Person recovered - resetting event")

        fall_confirmed = False
        fall_alert_sent = False

        fall_event_id = None
        fall_snapshot_path = None
        fall_occurred_at = None

        backend_event_sent = False
        last_backend_attempt = 0.0

        analyzer.confidence_history.clear()
        analyzer.last_fallen_detection = None

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
        # Load models
        
        detection_model, pose_model = load_models()
        analyzer = FallTemporalAnalyzer()
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

            annotated_frame, detections, fallen = object_detection(
                detection_model,
                pose_model,
                frame,
                analyzer
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
