from src.ai_engine.model_manager import ModelManager
from src.central_server.camera_manager import CameraManager
from src.central_server.event_manager import EventManager
from src.pc.ESP32_CAM_DETECTION_PUB_BACKUP_v2 import (
    setup_mqtt,
    shutdown_mqtt
)


class CentralAIServer:

    def __init__(self):
        self.model_manager = ModelManager()

        self.detection_model = None
        self.pose_model = None

        self.camera_manager = None
        self.event_manager = EventManager()

        self.is_initialized = False

    def initialize(self):
        if self.is_initialized:
            print("[SERVER] Central AI Server already initialized.")
            return

        print("\n========== CENTRAL AI SERVER ==========")

        # 1. Load AI models
        print("\n[SERVER] Loading AI models...")

        self.detection_model, self.pose_model = (
            self.model_manager.load_models()
        )

        print("[SERVER] Both AI models loaded successfully.")

        # 2. Initialize MQTT
        print("\n[SERVER] Initializing MQTT...")

        setup_mqtt()

        # 3. Initialize CameraManager
        print("\n[SERVER] Initializing CameraManager...")

        self.camera_manager = CameraManager(
            detection_model=self.detection_model,
            pose_model=self.pose_model,
            event_manager=self.event_manager
        )

        self.is_initialized = True

        print("\n[SERVER] Initialization completed!")

    def add_camera(self, camera_id: int, device_id: str, stream_url: str):
        if not self.is_initialized:
            raise RuntimeError(
                "Central AI Server has not been initialized."
            )

        return self.camera_manager.add_camera(
            camera_id=camera_id,
            device_id=device_id,
            stream_url=stream_url
        )

    def start_camera(self, camera_id: int):
        if not self.is_initialized:
            raise RuntimeError(
                "Central AI Server has not been initialized."
            )

        return self.camera_manager.start_camera(camera_id)

    def stop_camera(self, camera_id: int):
        if not self.is_initialized:
            raise RuntimeError(
                "Central AI Server has not been initialized."
            )

        return self.camera_manager.stop_camera(camera_id)
    def reset_camera_after_resolved(
        self,
        camera_id: int,
        event_id: str
    ):
        if not self.is_initialized:
            raise RuntimeError(
                "Central AI Server has not been initialized."
            )

        return self.camera_manager.reset_camera_after_resolved(
            camera_id=camera_id,
            event_id=event_id
        )
    def shutdown(self):
        print("\n[SERVER] Stopping Central AI Server...")

        if self.camera_manager is not None:
            camera_ids = list(
                self.camera_manager.get_all_cameras().keys()
            )

            for camera_id in camera_ids:
                try:
                    self.stop_camera(camera_id)
                except Exception as e:
                    print(
                        f"[SERVER] Error stopping camera "
                        f"{camera_id}: {e}"
                    )

        shutdown_mqtt()

        self.is_initialized = False

        print("[SERVER] Central AI Server stopped!")


if __name__ == "__main__":
    import time

    server = CentralAIServer()

    try:
        server.initialize()

        print("\n[SERVER] Central AI Server is ready!")
        print("[SERVER] Waiting for camera requests from Backend API...")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[SERVER] Keyboard interrupt received.")

    except Exception as e:
        print(f"\n[SERVER] Fatal error: {e}")

    finally:
        server.shutdown()