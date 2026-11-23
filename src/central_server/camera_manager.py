
from threading import Thread

from src.central_server.camera_session import CameraSession


class CameraManager:

    def __init__(self, detection_model, pose_model,event_manager):
        # Model dùng chung cho tất cả camera
        self.detection_model = detection_model
        self.pose_model = pose_model

        # Danh sách CameraSession, khóa bằng camera_id
        self.event_manager = event_manager
        self.cameras = {}
        self.camera_threads = {}

    def add_camera(self, camera_id: int, device_id: str, stream_url: str):
        if camera_id in self.cameras:
            print(
                f"[CAMERA MANAGER] Camera {camera_id} already exists"
            )
            return False

        camera = CameraSession(
            camera_id=camera_id,
            device_id=device_id,
            stream_url=stream_url,
            detection_model=self.detection_model,
            pose_model=self.pose_model,
            event_manager=self.event_manager
        )

        self.cameras[camera_id] = camera

        print(f"[CAMERA MANAGER] Added camera {camera_id}")

        return True
    def start_camera(self, camera_id: int):
        camera = self.cameras.get(camera_id)

        if camera is None:
            print(
                f"[CAMERA MANAGER] Camera {camera_id} not found"
            )
            return False

        camera_thread = self.camera_threads.get(camera_id)

        if camera_thread is not None and camera_thread.is_alive():
            print(
                f"[CAMERA MANAGER] Camera {camera_id} "
                "is already running"
            )
            return True
        camera.stop_event.clear()
        camera.is_running = True

        camera_thread = Thread(
            target=camera.run,
            daemon=True,
            name=f"CameraThread-{camera_id}"
        )

        self.camera_threads[camera_id] = camera_thread
        camera_thread.start()


        print(
            f"[CAMERA MANAGER] Started thread for camera {camera_id}"
        )

        return True

    def stop_camera(self, camera_id: int):
        camera = self.cameras.get(camera_id)

        if camera is None:
            return False

        camera_thread = self.camera_threads.get(camera_id)

        # Yêu cầu CameraSession dừng
        camera.is_running = False
        camera.stop_event.set()

        # Chờ thread kết thúc
        if camera_thread is not None and camera_thread.is_alive():
            camera_thread.join(timeout=10)

            if camera_thread.is_alive():
                print(
                    f"[CAMERA MANAGER] Camera {camera_id} "
                    "is still stopping"
                )
                return False

        # Đảm bảo giải phóng tài nguyên
        camera.disconnect()

        self.camera_threads.pop(camera_id, None)

        print(f"[CAMERA MANAGER] Stopped camera {camera_id}")

        return True
    def remove_camera(self, camera_id: int):
        camera = self.cameras.get(camera_id)

        if camera is None:
            return False

        # Dừng camera trước khi xóa
        if not self.stop_camera(camera_id):
            print(
                f"[CAMERA MANAGER] Cannot remove camera {camera_id}: "
                "camera is still running"
            )
            return False

        del self.cameras[camera_id]

        print(f"[CAMERA MANAGER] Removed camera {camera_id}")

        return True
    def get_camera(self, camera_id: int):
        return self.cameras.get(camera_id)

    def get_all_cameras(self):
        return self.cameras
    def reset_camera_after_resolved(
        self,
        camera_id: int,
        event_id: str
    ):
        camera = self.get_camera(camera_id)

        if camera is None:
            print(f"[RESET] Camera {camera_id} not found")
            return False

        # Đồng bộ với quá trình xử lý frame
        with camera.state_lock:

            event_state = camera.event_state

            # Chỉ reset đúng sự kiện đang được xử lý
            if event_state.fall_event_id != event_id:
                print(
                    f"[RESET] Event mismatch - "
                    f"Camera {camera_id}: {event_id}"
                )
                return False

            # 1. Reset CameraEventState
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

            event_state.last_alert_time = 0.0
            event_state.last_publish_attempt = 0.0

            # 2. Reset FallTemporalAnalyzer
            camera.analyzer.__init__()

        print(
            f"[RESET] Camera {camera_id} reset successfully "
            f"after RESOLVED: {event_id}"
        )

        return True