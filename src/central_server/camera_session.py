
import cv2
import time
from src.ai_engine.temporal_analyzer import FallTemporalAnalyzer
from collections import deque
from src.pc.ESP32_CAM_DETECTION_PUB_BACKUP_v2 import object_detection
from src.central_server.frame_buffer import FrameBuffer
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
        self.previous_hip_y = None
        self.previous_time = None
        self.last_fallen_detection = None

class CameraSession:

    def __init__(
        self,
        camera_id: int,
        stream_url: str,
        detection_model,
        pose_model
    ):
        self.camera_id = camera_id
        self.stream_url = stream_url

        # Sử dụng model được chia sẻ từ ModelManager
        self.detection_model = detection_model
        self.pose_model = pose_model

        # Mỗi camera có bộ phân tích riêng
        self.analyzer = FallTemporalAnalyzer()
        self.event_state = CameraEventState()

        self.cap = None
        self.is_running = False
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

        self.cap = cv2.VideoCapture(
            self.stream_url,
            cv2.CAP_FFMPEG
        )

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

        annotated_frame, detections, fallen = object_detection(
            self.detection_model,
            self.pose_model,
            frame,
            self.analyzer,
            self.event_state
        )

        # Cập nhật frame đã được AI xử lý vào FrameBuffer
        self.frame_buffer.update(annotated_frame)

        return annotated_frame, detections, fallen
    def run(self):
        if not self.is_running:
            print(f"[CAMERA {self.camera_id}] Camera is not running")
            return

        print(f"[CAMERA {self.camera_id}] Starting processing loop...")

        window_name = f"Fall Detection - Camera {self.camera_id}"

        try:
            while self.is_running:

                # 1. Nếu camera chưa kết nối, thử kết nối lại
                if self.cap is None or self.status == "offline":
                    if not self.connect():
                        print(
                            f"[CAMERA {self.camera_id}] "
                            "Retrying in 5 seconds..."
                        )
                        time.sleep(5)
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

                cv2.imshow(window_name, annotated_frame)

                # 4. Cho phép nhấn Q để dừng demo
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print(
                        f"[CAMERA {self.camera_id}] "
                        "User requested stop"
                    )
                    self.is_running = False
                    break

        except Exception as e:
            print(f"[CAMERA {self.camera_id}] Processing error: {e}")

        finally:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            self.status = "offline"
            self.is_running = False

            try:
                cv2.destroyWindow(window_name)
            except cv2.error:
                pass

            print(f"[CAMERA {self.camera_id}] Processing stopped")