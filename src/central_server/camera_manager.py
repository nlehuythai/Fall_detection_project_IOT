
from threading import Thread

from src.central_server.camera_session import CameraSession


class CameraManager:

    def __init__(self, detection_model, pose_model):
        # Model dùng chung cho tất cả camera
        self.detection_model = detection_model
        self.pose_model = pose_model

        # Danh sách CameraSession, khóa bằng camera_id
        self.cameras = {}
        self.camera_threads = {}

    def add_camera(self, camera_id: int, stream_url: str):
        if camera_id in self.cameras:
            print(
                f"[CAMERA MANAGER] Camera {camera_id} already exists"
            )
            return False

        camera = CameraSession(
            camera_id=camera_id,
            stream_url=stream_url,
            detection_model=self.detection_model,
            pose_model=self.pose_model
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

        if camera_thread is not None:
            if camera_thread.is_alive():
                camera.is_running = False

                camera_thread.join(timeout=10)

                if camera_thread.is_alive():
                    print(
                        f"[CAMERA MANAGER] Camera {camera_id} "
                        "is still stopping"
                    )
                    return False

        else:
            camera.disconnect()

        self.camera_threads.pop(camera_id, None)

        print(f"[CAMERA MANAGER] Stopped camera {camera_id}")

        return True

    def remove_camera(self, camera_id: int):
        camera = self.cameras.get(camera_id)

        if camera is None:
            return False

        camera.disconnect()
        del self.cameras[camera_id]

        print(f"[CAMERA MANAGER] Removed camera {camera_id}")

        return True

    def get_camera(self, camera_id: int):
        return self.cameras.get(camera_id)

    def get_all_cameras(self):
        return self.cameras
