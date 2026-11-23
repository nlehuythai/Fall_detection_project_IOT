
import cv2
import time
from src.ai_engine.temporal_analyzer import FallTemporalAnalyzer
from collections import deque
from src.pc.ESP32_CAM_DETECTION_PUB_BACKUP_v2 import object_detection
from src.central_server.frame_buffer import FrameBuffer
from threading import Event,Lock
class CameraEventState:

    def __init__(self):
        self.last_alert_time = 0.0
        self.last_publish_attempt = 0.0

        self.fall_confirmed = False
        self.fall_alert_sent = False

        self.fall_event_id = None
        self.fall_snapshot_path = None
        self.fall_occurred_at = None

        self.backend_event_sent = False
        self.last_backend_attempt = 0.0

        self.confidence_history = deque(maxlen=15)
        self.previous_hip_x = None
        self.previous_hip_y = None
        self.previous_time = None
        self.last_fallen_detection = None


class CameraSession:

    def __init__(
        self,
        camera_id: int,
        device_id: str,
        stream_url: str,
        detection_model,
        pose_model,
        event_manager
    ):
        self.camera_id = camera_id
        self.device_id = device_id
        self.stream_url = stream_url

        # Sử dụng model được chia sẻ từ ModelManager
        self.detection_model = detection_model
        self.pose_model = pose_model
        self.event_manager = event_manager

        # Mỗi camera có bộ phân tích riêng
        self.analyzer = FallTemporalAnalyzer()
        self.event_state = CameraEventState()
        self.state_lock = Lock()

        self.cap = None
        self.is_running = False
        self.stop_event = Event()
        self.status = "offline"
        self.frame_buffer = FrameBuffer()

    def connect(self):
        # Giải phóng kết nối cũ nếu còn tồn tại
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.status = "offline"

        print(
            f"[CAMERA {self.camera_id}] "
            f"Connecting to {self.stream_url}"
        )

        camera_source = self.stream_url
        print(
            f"[DEBUG] stream_url={self.stream_url}, "
            f"type={type(self.stream_url)}"
        )
        if (
            isinstance(camera_source, int)
            or (
                isinstance(camera_source, str)
                and camera_source.isdigit()
            )
        ):
            camera_source = int(camera_source)
            backend = cv2.CAP_DSHOW
        else:
            backend = cv2.CAP_FFMPEG

        self.cap = cv2.VideoCapture(
            camera_source,
            backend
        )
        if backend == cv2.CAP_FFMPEG:
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)

        if not self.cap.isOpened():
            print(
                f"[CAMERA {self.camera_id}] "
                "Cannot open stream"
            )

            self.cap.release()
            self.cap = None
            self.status = "offline"
            return False

        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        success, frame = self.cap.read()

        if not success or frame is None:
            print(
                f"[CAMERA {self.camera_id}] "
                "Cannot read initial frame"
            )

            self.cap.release()
            self.cap = None
            self.status = "offline"
            return False

        self.status = "online"

        print(f"[CAMERA {self.camera_id}] Connected")
        print(
            f"[CAMERA {self.camera_id}] "
            f"Initial frame: {frame.shape}"
        )

        return True   
    def disconnect(self):
        self.is_running = False
        self.stop_event.set()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.status = "offline"

        print(f"[CAMERA {self.camera_id}] Disconnected")

    def read_frame(self):
        if not self.is_running or self.cap is None:
            return None

        success, frame = self.cap.read()

        if not success or frame is None:
            print(
                f"[CAMERA {self.camera_id}] "
                "Failed to read frame from stream"
            )

            self.status = "offline"
            return None

        return frame
    def process_frame(self):
        frame = self.read_frame()

        if frame is None:
            return None
        with self.state_lock:
            annotated_frame, detections, fallen = object_detection(
                self.detection_model,
                self.pose_model,
                frame,
                self.analyzer,
                self.event_state,
                event_manager=self.event_manager,
                camera_id=self.camera_id,
                device_id=self.device_id
            )

        # Cập nhật frame đã được AI xử lý vào FrameBuffer
        self.frame_buffer.update(annotated_frame)

        return annotated_frame, detections, fallen
    def run(self):
        if not self.is_running:
            print(f"[CAMERA {self.camera_id}] Camera is not running")
            return
        self.analyzer = FallTemporalAnalyzer()

# Reset lịch sử Hip để tránh vận tốc từ phiên trước
        self.event_state.previous_hip_y = None
        self.event_state.previous_time = None
        self.stop_event.clear()

        print(f"[CAMERA {self.camera_id}] Starting processing loop...")



        try:
            while self.is_running and not self.stop_event.is_set():

                # 1. Nếu camera chưa kết nối, thử kết nối lại
                if self.cap is None or self.status == "offline":
                    if not self.connect():
                        print(
                            f"[CAMERA {self.camera_id}] "
                            "Retrying in 5 seconds..."
                        )
                        if self.stop_event.wait(5):
                            break

                        continue

                # 2. Đọc và xử lý frame
                result = self.process_frame()

                # 3. Nếu mất kết nối, giải phóng stream và thử lại
                if result is None:
                    print(
                        f"[CAMERA {self.camera_id}] "
                        "Stream lost. Reconnecting..."
                    )

                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None

                    self.status = "offline"
                    time.sleep(5)
                    continue

                annotated_frame, detections, fallen = result

        except Exception as e:
            print(f"[CAMERA {self.camera_id}] Processing error: {e}")

        finally:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            self.status = "offline"
            self.is_running = False

            print(f"[CAMERA {self.camera_id}] Processing stopped")