
from pathlib import Path
from ultralytics import YOLO
import torch


def main():
    ROOT_DIR = Path(__file__).resolve().parent

    DATA_YAML = (
        ROOT_DIR
        / "training"
        / "dataset_v2_yolo_split_v2"
        / "data.yaml"
    )

    MODEL_WEIGHTS = "yolo11n.pt"
    PROJECT_DIR = ROOT_DIR / "training" / "results"

    print("=" * 60)
    print("YOLO11 FALL DETECTION - TRAINING")
    print("=" * 60)

    print("PyTorch:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA không khả dụng!")

    print("GPU:", torch.cuda.get_device_name(0))

    if not DATA_YAML.exists():
        raise FileNotFoundError(f"Không tìm thấy: {DATA_YAML}")

    print("\nLoading pretrained model...")
    model = YOLO(MODEL_WEIGHTS)

    print("\nStarting training...")

    model.train(
        data=str(DATA_YAML),

        epochs=80,
        imgsz=640,
        batch=2,

        device=0,

        # Windows: tắt multiprocessing
        workers=0,

        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,

        patience=20,
        cos_lr=True,

        amp=True,
        cache=False,
        close_mosaic=10,

        project=str(PROJECT_DIR),
        name="fall_detection_yolo11n_v1",
        exist_ok=True,

        plots=True,
        save=True,
        save_period=10,

        verbose=True
    )

    print("\nTRAINING COMPLETED")


if __name__ == "__main__":
    main()
