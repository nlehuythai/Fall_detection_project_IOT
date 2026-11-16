
from pathlib import Path
from ultralytics import YOLO
import torch


def main():
    ROOT = Path(__file__).resolve().parent

    CHECKPOINT = (
        ROOT
        / "training"
        / "results"
        / "fall_detection_yolo11n_v1"
        / "weights"
        / "last.pt"
    )

    if not CHECKPOINT.exists():
        raise FileNotFoundError(
            f"Không tìm thấy checkpoint: {CHECKPOINT}"
        )

    print("=" * 60)
    print("RESUME YOLO11 TRAINING")
    print("=" * 60)

    print("PyTorch:", torch.__version__)
    print("CUDA:", torch.cuda.is_available())

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA không khả dụng!")

    print("GPU:", torch.cuda.get_device_name(0))
    print("Checkpoint:", CHECKPOINT)

    model = YOLO(str(CHECKPOINT))

    print("\nResuming training...")

    # Khôi phục optimizer, scheduler và epoch từ checkpoint.
    model.train(
        resume=True,
        cache="disk"
    )

    print("\nRESUME TRAINING COMPLETED")


if __name__ == "__main__":
    main()