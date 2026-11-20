from src.ai_engine.model_manager import ModelManager
from src.central_server.camera_manager import CameraManager
from src.central_server.event_manager import EventManager


class CentralAIServer:

    def __init__(self):
        self.model_manager = ModelManager()

        self.detection_model = None
        self.pose_model = None

        self.camera_manager = None
        self.event_manager = EventManager()

    def initialize(self):
        print("\n========== CENTRAL AI SERVER ==========")

        # 1. Load YOLO models
        print("\n[SERVER] Loading AI models...")

        self.detection_model, self.pose_model = (
            self.model_manager.load_models()
        )

        # 2. Initialize CameraManager
        print("\n[SERVER] Initializing CameraManager...")

        self.camera_manager = CameraManager(
            detection_model=self.detection_model,
            pose_model=self.pose_model
        )

        print("\n[SERVER] Initialization completed!")

    def add_camera(self, camera_id, stream_url):
        return self.camera_manager.add_camera(
            camera_id=camera_id,
            stream_url=stream_url
        )

    def start_camera(self, camera_id):
        return self.camera_manager.start_camera(camera_id)

    def stop_camera(self, camera_id):
        return self.camera_manager.stop_camera(camera_id)

    def shutdown(self):
        print("\n[SERVER] Stopping Central AI Server...")

        if self.camera_manager is not None:
            camera_ids = list(
                self.camera_manager.get_all_cameras().keys()
            )

            for camera_id in camera_ids:
                self.stop_camera(camera_id)

        print("[SERVER] Central AI Server stopped!")