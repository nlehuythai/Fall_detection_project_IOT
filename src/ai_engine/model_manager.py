
import os
from pathlib import Path

from dotenv import load_dotenv
from ultralytics import YOLO


class ModelManager:
    def __init__(self):
        self.root_dir = Path(__file__).resolve().parents[2]

        # Load cấu hình từ .env
        load_dotenv(self.root_dir / ".env")

        # Detection model
        default_model = (
            self.root_dir
            / "training"
            / "results"
            / "fall_detection_yolo11n_v1"
            / "weights"
            / "best.pt"
        )

        self.detection_model_path = Path(
            os.getenv("MODEL_PATH", str(default_model))
        )

        if not self.detection_model_path.is_absolute():
            self.detection_model_path = (
                self.root_dir / self.detection_model_path
            )

        # Pose model
        self.pose_model_path = (
            self.root_dir
            / "training"
            / "results"
            / "fall_detection_yolo11n_v1"
            / "weights"
            / "yolo11n-pose.pt"
        )

        self.detection_model = None
        self.pose_model = None

        self.class_names = {
            0: "Fallen",
            1: "Non-fallen"
        }

    def load_models(self):
        # Không load lại nếu model đã tồn tại
        if (
            self.detection_model is not None
            and self.pose_model is not None
        ):
            print("[MODEL] Models already loaded")
            return self.detection_model, self.pose_model

        # Kiểm tra Detection model
        if not self.detection_model_path.exists():
            raise FileNotFoundError(
                f"Detection model not found: "
                f"{self.detection_model_path}"
            )

        # Kiểm tra Pose model
        if not self.pose_model_path.exists():
            raise FileNotFoundError(
                f"Pose model not found: "
                f"{self.pose_model_path}"
            )

        print("[MODEL] Loading Detection model...")
        self.detection_model = YOLO(
            str(self.detection_model_path)
        )

        # Kiểm tra class mapping
        names = self.detection_model.names

        for class_id, expected_name in self.class_names.items():
            actual_name = names.get(class_id)

            if actual_name != expected_name:
                raise ValueError(
                    f"Incorrect class mapping! "
                    f"Expected {class_id}: {expected_name}, "
                    f"got {actual_name}"
                )

        print("[MODEL] Detection model loaded and verified")

        print("[MODEL] Loading Pose model...")
        self.pose_model = YOLO(
            str(self.pose_model_path)
        )

        print("[MODEL] Pose model loaded")
        print("[MODEL] Both models loaded successfully")

        return self.detection_model, self.pose_model
