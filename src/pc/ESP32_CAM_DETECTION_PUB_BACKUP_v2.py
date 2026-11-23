import json
import math
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

SNAPSHOT_DIR = ROOT_DIR / "data" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

CENTRAL_AI_API_KEY = os.getenv("CENTRAL_AI_API_KEY")

BACKEND_INTERNAL_EVENT_URL = (
    f"{BACKEND_API_URL}/households/internal/cameras"
)

MQTT_BROKER = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "esp32/camera/detection")
MQTT_CLIENT_ID = os.getenv(
    "MQTT_CLIENT_ID",
    "Central_AI_Server_Publisher"
)

KEYPOINT_THRESHOLD = 0.3
POSE_CONF_THRESHOLD = 0.25

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

CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.5"))
IMAGE_SIZE = 640

FALL_COOLDOWN_SECONDS = 5
ALERT_RETRY_INTERVAL = 2.0
BACKEND_RETRY_INTERVAL = 5.0

# Cho phép mất Pose trong khoảng ngắn.
# Nếu quá thời gian này, không dùng lại vị trí hông cũ.
POSE_GAP_GRACE_SECONDS = 0.35

mqtt_client = None


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
    previous_hip_x,
    previous_hip_y,
    previous_time
):
    """
    Trích xuất:
    - Góc thân người.
    - Vị trí hông X, Y.
    - Tốc độ hông 2D.
    - Độ tin cậy keypoint.
    """

    if result.keypoints is None:
        return None

    if len(result.keypoints) == 0:
        return None

    if result.keypoints.conf is None:
        return None

    keypoints = result.keypoints.xy[0].cpu().numpy()
    keypoint_conf = result.keypoints.conf[0].cpu().numpy()

    if len(keypoint_conf) <= max(REQUIRED_POINTS):
        return None

    # Kiểm tra độ tin cậy của vai và hông.
    if not all(
        keypoint_conf[i] > KEYPOINT_THRESHOLD
        for i in REQUIRED_POINTS
    ):
        return None

    angle, hip = calculate_torso_angle(keypoints)

    current_time = time.time()

    current_hip_x = float(hip[0])
    current_hip_y = float(hip[1])

    # --------------------------------------------------------
    # HIP VELOCITY 2D
    # --------------------------------------------------------

    hip_velocity = 0.0

    if (
        previous_hip_x is not None
        and previous_hip_y is not None
        and previous_time is not None
    ):

        delta_time = current_time - previous_time

        if delta_time > 0:

            delta_x = current_hip_x - previous_hip_x
            delta_y = current_hip_y - previous_hip_y

            hip_velocity = (
                math.sqrt(delta_x ** 2 + delta_y ** 2)
                / delta_time
            )

    average_confidence = float(
        np.mean([
            keypoint_conf[i]
            for i in REQUIRED_POINTS
        ])
    )

    return {
        "torso_angle": float(angle),
        "hip_x": current_hip_x,
        "hip_y": current_hip_y,
        "hip_velocity": float(hip_velocity),
        "keypoint_confidence": average_confidence,
        "keypoints": keypoints,
        "keypoint_scores": keypoint_conf,
        "timestamp": current_time
    }

# ============================================================
# MQTT LIFECYCLE
# ============================================================

def on_mqtt_connect(client, userdata, flags, rc):

    if rc == 0:
        print("[MQTT] Connected successfully")
        print(f"[MQTT] Topic: {MQTT_TOPIC}")

    else:
        print(f"[MQTT] Connection failed: {rc}")


def on_mqtt_disconnect(client, userdata, rc):

    if rc != 0:
        print(
            f"[MQTT] Unexpected disconnection: {rc}"
        )


def setup_mqtt():
    """
    Khởi tạo MQTT publisher một lần từ CentralAIServer.initialize().
    Không gọi hàm này trong từng CameraSession.
    """

    global mqtt_client

    if mqtt_client is not None:

        try:
            if mqtt_client.is_connected():
                return mqtt_client

        except Exception:
            pass

    try:

        client = mqtt.Client(
            client_id=MQTT_CLIENT_ID
        )

        client.on_connect = on_mqtt_connect
        client.on_disconnect = on_mqtt_disconnect

        print(
            f"[MQTT] Connecting to "
            f"{MQTT_BROKER}:{MQTT_PORT}..."
        )

        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            60
        )

        client.loop_start()

        mqtt_client = client

        return mqtt_client

    except Exception as error:

        print(
            f"[MQTT] Connection error: {error}"
        )

        mqtt_client = None

        return None


def shutdown_mqtt():
    """
    Ngắt MQTT publisher khi CentralAIServer shutdown.
    """

    global mqtt_client

    if mqtt_client is None:
        return

    try:

        mqtt_client.loop_stop()
        mqtt_client.disconnect()

        print(
            "[MQTT] Publisher disconnected"
        )

    except Exception as error:

        print(
            f"[MQTT] Shutdown error: {error}"
        )

    finally:

        mqtt_client = None


# ============================================================
# SNAPSHOT
# ============================================================

def save_fall_snapshot(frame, event_id):

    if frame is None:

        print(
            "[SNAPSHOT] Empty frame. Cannot save image."
        )

        return None

    try:

        now = datetime.now()

        date_folder = (
            SNAPSHOT_DIR
            / str(now.year)
            / f"{now.month:02d}"
            / f"{now.day:02d}"
        )

        date_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        image_path = (
            date_folder
            / f"{event_id}.jpg"
        )

        height, width = frame.shape[:2]

        if width > 1280:

            new_height = int(
                height * 1280 / width
            )

            snapshot_frame = cv2.resize(
                frame,
                (1280, new_height),
                interpolation=cv2.INTER_AREA
            )

        else:

            snapshot_frame = frame

        success = cv2.imwrite(
            str(image_path),
            snapshot_frame,
            [cv2.IMWRITE_JPEG_QUALITY, 80]
        )

        if not success:

            print(
                "[SNAPSHOT] Failed to save image."
            )

            return None

        file_size_kb = (
            image_path.stat().st_size / 1024
        )

        print(
            f"[SNAPSHOT] Image size: "
            f"{file_size_kb:.2f} KB"
        )

        print(
            f"[SNAPSHOT] Saved: {image_path}"
        )

        return image_path

    except Exception as error:

        print(
            f"[SNAPSHOT ERROR] {error}"
        )

        return None


# ============================================================
# MQTT EVENT PUBLISHING
# ============================================================

def publish_detection(
    detections,
    average_confidence,
    elapsed_time,
    event_id=None,
    snapshot_path=None,
    camera_id=None,
    device_id=None
):

    if not detections:
        return False
    if not device_id:
        print(
            "[MQTT] Missing device_id. Alert not sent."
        )
        return False
    if (
        mqtt_client is None
        or not mqtt_client.is_connected()
    ):

        print(
            "[MQTT] Not connected. Alert not sent."
        )

        return False

    try:

        camera_label = (
            f"Camera {camera_id}"
            if camera_id is not None
            else "Central AI Camera"
        )

        payload_data = {
            "device_id": device_id,
            "camera_id": camera_id,
            "event": "FALL_DETECTED",
            "camera": camera_label,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds"),
            "fall_duration_seconds": round(
                elapsed_time,
                2
            ),
            "average_confidence": round(
                average_confidence,
                3
            ),
            "detections": detections,
            "event_id": event_id,
            "snapshot_path": (
                str(snapshot_path)
                if snapshot_path
                else None
            )
        }

        result = mqtt_client.publish(
            MQTT_TOPIC,
            json.dumps(payload_data),
            qos=1
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            print(
                f"[MQTT] FALL ALERT published "
                f"({camera_label})"
            )

            return True

        print(
            f"[MQTT] Publish failed: {result.rc}"
        )

        return False

    except Exception as error:

        print(
            f"[MQTT] Publish error: {error}"
        )

        return False


# ============================================================
# BACKEND EVENT SUBMISSION
# ============================================================

def send_event_to_backend(
    event_id,
    occurred_at,
    elapsed_time,
    average_confidence,
    snapshot_path=None,
    camera_id=None,
    device_id=None
):

    if not CENTRAL_AI_API_KEY:

        print(
            "[BACKEND] CENTRAL_AI_API_KEY is not configured."
        )

        return False

    if camera_id is None:

        print(
            "[BACKEND] camera_id is missing."
        )

        return False

    snapshot_key = None

    if snapshot_path:

        try:

            snapshot_key = Path(
                snapshot_path
            ).relative_to(
                SNAPSHOT_DIR
            ).as_posix()

        except ValueError:

            print(
                "[SNAPSHOT] Cannot create relative snapshot path."
            )

            return False

    payload = {
        "event_id": event_id,
        "occurred_at": occurred_at.isoformat(
            timespec="seconds"
        ),
        "fall_duration_seconds": round(
            elapsed_time,
            2
        ),
        "average_confidence": round(
            average_confidence,
            3
        ),
        "snapshot_key": snapshot_key
    }

    headers = {
        "X-Internal-API-Key": CENTRAL_AI_API_KEY
    }

    event_url = (
        f"{BACKEND_INTERNAL_EVENT_URL}/{camera_id}/events"
    )

    try:

        response = requests.post(
            event_url,
            json=payload,
            headers=headers,
            timeout=5
        )

        if response.status_code in (200, 201):

            print(
                f"[BACKEND] Fall event saved successfully "
                f"(Camera {camera_id})."
            )

            return True

        if response.status_code == 409:

            print(
                "[BACKEND] Event already exists."
            )

            return True

        print(
            f"[BACKEND] Submission failed: "
            f"HTTP {response.status_code} - {response.text}"
        )

        return False

    except requests.RequestException as error:

        print(
            f"[BACKEND] Request error: {error}"
        )

        return False


# ============================================================
# OBJECT DETECTION
# ============================================================

def object_detection(
    detection_model,
    pose_model,
    frame,
    analyzer,
    event_state,
    event_manager=None,
    camera_id=None,
    device_id=None
):

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

            class_id = int(
                box.cls[0].item()
            )

            class_name = detection_result.names[class_id]

            confidence = float(
                box.conf[0].item()
            )

            x1, y1, x2, y2 = (
                box.xyxy[0].tolist()
            )

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
                "Probability": round(
                    confidence,
                    3
                ),
                "X Center": round(
                    (x1 + box_width / 2) / image_width,
                    3
                ),
                "Y Center": round(
                    (y1 + box_height / 2) / image_height,
                    3
                ),
                "Width": round(
                    box_width / image_width,
                    3
                ),
                "Height": round(
                    box_height / image_height,
                    3
                )
            }

            detections.append(detection)

            # Không phụ thuộc cứng vào class_id == 0.
            # Kiểm tra tên class để tránh sai mapping.
            if class_name.strip().lower() == "fallen":

                fallen_detections.append(detection)

    # --------------------------------------------------------
    # SELECT DETECTION
    # --------------------------------------------------------

    # Ưu tiên Fallen nếu có.
    # Tránh trường hợp Non-fallen có confidence cao hơn
    # ghi đè kết quả Fallen.
    if fallen_detections:

        selected_detection = max(
            fallen_detections,
            key=lambda item: item["Probability"]
        )

        detection_class = "Fallen"

        detection_confidence = (
            selected_detection["Probability"]
        )

    elif detections:

        selected_detection = max(
            detections,
            key=lambda item: item["Probability"]
        )

        detection_class = (
            selected_detection["Object type"]
        )

        detection_confidence = (
            selected_detection["Probability"]
        )

    # --------------------------------------------------------
    # CACHE FALLEN DETECTION
    # --------------------------------------------------------

    if not hasattr(
        event_state,
        "confidence_history"
    ):

        event_state.confidence_history = deque(
            maxlen=15
        )

        event_state.last_fallen_detection = None

    if detection_class == "Fallen":

        event_state.confidence_history.append(
            detection_confidence
        )

        if fallen_detections:

            event_state.last_fallen_detection = max(
                fallen_detections,
                key=lambda item: item["Probability"]
            )

    # ========================================================
    # 2. YOLO POSE
    # ========================================================

    pose_results = pose_model.predict(
        source=frame,
        imgsz=IMAGE_SIZE,
        conf=POSE_CONF_THRESHOLD,
        verbose=False
    )

    pose_result = pose_results[0]

    if pose_result.keypoints is None:

        print(
            "[POSE DEBUG] No keypoints detected"
        )

    # elif len(pose_result.keypoints) == 0:

    #     print(
    #         "[POSE DEBUG] Empty keypoints"
    #     )

    # --------------------------------------------------------
    # HANDLE SHORT POSE INTERRUPTION
    # --------------------------------------------------------

    current_pose_time = time.time()

    if not hasattr(
        event_state,
        "pose_gap_started_at"
    ):

        event_state.pose_gap_started_at = None

    pose_gap_duration = 0.0

    if event_state.pose_gap_started_at is not None:

        pose_gap_duration = (
            current_pose_time
            - event_state.pose_gap_started_at
        )

        if pose_gap_duration > POSE_GAP_GRACE_SECONDS:
            event_state.previous_hip_x = None
            event_state.previous_hip_y = None
            event_state.previous_time = None

    # --------------------------------------------------------
    # EXTRACT POSE FEATURES
    # --------------------------------------------------------

    pose_features = extract_pose_features(
        pose_result,
        event_state.previous_hip_x,
        event_state.previous_hip_y,
        event_state.previous_time
    )

    if pose_features is not None:

        event_state.previous_hip_x = (
            pose_features["hip_x"]
        )

        event_state.previous_hip_y = (
            pose_features["hip_y"]
        )

        event_state.previous_time = (
            pose_features["timestamp"]
        )

        event_state.pose_gap_started_at = None
    else:

        if event_state.pose_gap_started_at is None:

            event_state.pose_gap_started_at = (
                current_pose_time
            )

        if (
            current_pose_time
            - event_state.pose_gap_started_at
            > POSE_GAP_GRACE_SECONDS
        ):
            event_state.previous_hip_x = None
            event_state.previous_hip_y = None
            event_state.previous_time = None

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

    elif state in (
        "FALL_TRANSITION",
        "POSTURE_VERIFICATION"
    ):

        state_color = (0, 165, 255)

    else:

        state_color = (0, 255, 0)

    # --------------------------------------------------------
    # DRAW DETECTION BOXES
    # --------------------------------------------------------

    for detection in detections:

        x1, y1, x2, y2 = (
            detection["Coordinates"]
        )

        color = (
            (0, 0, 255)
            if detection["Object type"].strip().lower() == "fallen"
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

    # --------------------------------------------------------
    # DISPLAY INFORMATION
    # --------------------------------------------------------

    if pose_features is not None:

        torso_angle_text = (
            f"Torso angle: "
            f"{pose_features['torso_angle']:.1f}"
        )

    else:

        torso_angle_text = (
            "Torso angle: unavailable"
        )

    display_lines = [

        (
            f"Detection: {detection_class} "
            f"({detection_confidence:.2f})",
            (255, 255, 0)
        ),

        (
            f"State: {state}",
            state_color
        ),

        (
            f"Fallen ratio: "
            f"{analysis['fallen_ratio']:.2f}",
            (255, 255, 255)
        ),

        (
            torso_angle_text,
            (255, 255, 255)
        ),

        (
            f"Average velocity: "
            f"{analysis['average_velocity']:.1f} px/s",
            (255, 255, 255)
        ),

        (
            f"Peak downward velocity: "
            f"{analysis['peak_downward_velocity']:.1f} px/s",
            (255, 255, 255)
        ),

        (
            f"Low duration: "
            f"{analysis['low_duration']:.1f}s",
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

    if (
        state == "FALL_CONFIRMED"
        and not event_state.fall_confirmed
    ):

        event_state.fall_confirmed = True

        print(
            "[ALERT] FALL CONFIRMED!"
        )

        event_state.fall_event_id = (
            f"FALL_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}"
        )

        # Register event in shared EventManager.
        if (
            event_manager is not None
            and camera_id is not None
        ):

            registered = event_manager.register_event(
                camera_id,
                event_state.fall_event_id
            )

            if registered:

                print(
                    f"[EVENT] Registered fall event "
                    f"from Camera {camera_id}"
                )

            else:

                print(
                    f"[EVENT] Event already registered: "
                    f"{event_state.fall_event_id}"
                )

        event_state.fall_occurred_at = (
            datetime.now(timezone.utc)
        )

        event_state.fall_snapshot_path = (
            save_fall_snapshot(
                frame,
                event_state.fall_event_id
            )
        )

        event_state.fall_alert_sent = False
        event_state.backend_event_sent = False
        event_state.last_backend_attempt = 0.0

    # --------------------------------------------------------
    # AVERAGE FALLEN CONFIDENCE
    # --------------------------------------------------------

    average_confidence = (

        sum(event_state.confidence_history)
        / len(event_state.confidence_history)

        if event_state.confidence_history

        else detection_confidence
    )

    elapsed_time = analysis["low_duration"]

    # ========================================================
    # 6. SEND MQTT ALERT
    # ========================================================

    if (
        event_state.fall_confirmed
        and not event_state.fall_alert_sent
    ):

        cooldown_ok = (
            current_time - event_state.last_alert_time
            >= FALL_COOLDOWN_SECONDS
        )

        retry_ok = (
            current_time - event_state.last_publish_attempt
            >= ALERT_RETRY_INTERVAL
        )

        if cooldown_ok and retry_ok:

            event_state.last_publish_attempt = (
                current_time
            )

            cached_detection = (
                event_state.last_fallen_detection
            )

            if cached_detection is not None:

                if publish_detection(
                    [cached_detection],
                    average_confidence,
                    elapsed_time,
                    event_state.fall_event_id,
                    event_state.fall_snapshot_path,
                    camera_id=camera_id,
                    device_id=device_id
                ):

                    event_state.last_alert_time = (
                        current_time
                    )

                    event_state.fall_alert_sent = True

                    print(
                        "[ALERT] MQTT notification accepted"
                    )

                else:

                    print(
                        "[ALERT] MQTT failed - will retry"
                    )

    # ========================================================
    # 7. SEND FALL EVENT TO BACKEND
    # ========================================================

    if (
        event_state.fall_confirmed
        and not event_state.backend_event_sent
    ):

        if (
            current_time - event_state.last_backend_attempt
            >= BACKEND_RETRY_INTERVAL
        ):

            event_state.last_backend_attempt = (
                current_time
            )

            if send_event_to_backend(
                event_state.fall_event_id,
                event_state.fall_occurred_at,
                elapsed_time,
                average_confidence,
                snapshot_path=event_state.fall_snapshot_path,
                camera_id=camera_id,
                device_id=device_id
            ):

                event_state.backend_event_sent = True

                print(
                    "[BACKEND] Event synchronized successfully."
                )

            else:

                print(
                    "[BACKEND] Failed - will retry."
                )

    # ========================================================
    # 8. RESET AFTER RECOVERY
    # ========================================================

    if state == "RECOVERED":

        print(
            "[ALERT] Person recovered - resetting event"
        )

        event_state.fall_confirmed = False
        event_state.fall_alert_sent = False

        event_state.fall_event_id = None
        event_state.fall_snapshot_path = None
        event_state.fall_occurred_at = None

        event_state.backend_event_sent = False
        event_state.last_backend_attempt = 0.0

        event_state.confidence_history.clear()
        event_state.last_fallen_detection = None
        event_state.previous_hip_x = None
        event_state.previous_hip_y = None
        event_state.previous_time = None
        event_state.pose_gap_started_at = None

    return (
        annotated_frame,
        detections,
        fallen_detections
    )