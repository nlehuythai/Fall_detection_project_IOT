from pathlib import Path
from ultralytics import YOLO
import torch


def main():
    ROOT = Path(__file__).resolve().parent

    MODEL_PATH = (
        ROOT
        / "training"
        / "results"
        / "fall_detection_yolo11n_v1"
        / "weights"
        / "best.pt"
    )

    DATA_YAML = (
        ROOT
        / "training"
        / "dataset_v2_yolo_split_v2"
        / "data.yaml"
    )

    PROJECT_DIR = ROOT / "training" / "results"

    print("=" * 60)
    print("FALL DETECTION - TEST EVALUATION")
    print("=" * 60)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy model: {MODEL_PATH}")

    if not DATA_YAML.exists():
        raise FileNotFoundError(f"Không tìm thấy data.yaml: {DATA_YAML}")

    device = 0 if torch.cuda.is_available() else "cpu"

    print(f"Model: {MODEL_PATH}")
    print(f"Dataset: {DATA_YAML}")
    print(f"Device: {device}")

    model = YOLO(str(MODEL_PATH))

    metrics = model.val(
        data=str(DATA_YAML),
        split="test",
        imgsz=640,
        batch=2,
        device=device,
        workers=0,
        plots=True,
        project=str(PROJECT_DIR),
        name="fall_detection_test_evaluation",
        exist_ok=True,
        verbose=True
    )

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    print(f"Precision:    {metrics.box.mp:.4f}")
    print(f"Recall:       {metrics.box.mr:.4f}")
    print(f"mAP50:        {metrics.box.map50:.4f}")
    print(f"mAP50-95:     {metrics.box.map:.4f}")

    print("\nEvaluation completed.")
    print(f"Results saved at: {PROJECT_DIR}")


if __name__ == "__main__":
    main()