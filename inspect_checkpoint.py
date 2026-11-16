
from pathlib import Path
import torch

checkpoint = Path(
    "training/results/fall_detection_yolo11n_v1/weights/last.pt"
)

ckpt = torch.load(
    checkpoint,
    map_location="cpu",
    weights_only=False
)

print("=" * 60)
print("CHECKPOINT TRAINING CONFIGURATION")
print("=" * 60)

args = ckpt.get("train_args", {})

for key in [
    "data",
    "model",
    "epochs",
    "imgsz",
    "batch",
    "device",
    "workers",
    "optimizer",
    "lr0",
    "project",
    "name",
    "resume"
]:
    print(f"{key}: {args.get(key)}")

print("\nEpoch:", ckpt.get("epoch"))
print("Best fitness:", ckpt.get("best_fitness"))

print("\nTraining metrics:")
print(ckpt.get("train_metrics"))

print("\nTraining results:")
print(ckpt.get("train_results"))
