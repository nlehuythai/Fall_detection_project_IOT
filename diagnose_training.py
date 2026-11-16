
from pathlib import Path
import torch
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parent

# 1. Kiểm tra checkpoint
checkpoint = (
    ROOT / "training/results/fall_detection_yolo11n_v1/weights/last.pt"
)

print("=" * 60)
print("1. CHECKPOINT")
print("=" * 60)

if checkpoint.exists():
    ckpt = torch.load(
        checkpoint,
        map_location="cpu",
        weights_only=False
    )

    print("Checkpoint:", checkpoint)
    print("Size:", round(checkpoint.stat().st_size / 1024**2, 2), "MB")
    print("Epoch:", ckpt.get("epoch"))
    print("Best fitness:", ckpt.get("best_fitness"))
    print("Available keys:", list(ckpt.keys()))
else:
    print("Checkpoint not found!")

# 2. Kiểm tra cache
print("\n" + "=" * 60)
print("2. DATASET CACHE")
print("=" * 60)

cache_files = [
    ROOT / "training/dataset_v2_yolo_split_v2/labels/train.cache",
    ROOT / "training/dataset_v2_yolo_split_v2/labels/val.cache"
]

for cache_file in cache_files:
    print("\nCache:", cache_file)

    if not cache_file.exists():
        print("Cache not found!")
        continue

    try:
        data = np.load(cache_file, allow_pickle=True).item()

        print("Keys:", list(data.keys()))
        print("Cached labels:", len(data.get("labels", [])))

        missing = []

        for item in data.get("labels", []):
            image_path = Path(item["im_file"])

            if not image_path.exists():
                missing.append(str(image_path))

        print("Missing images in cache:", len(missing))

        for path in missing[:10]:
            print("  ", path)

    except Exception as e:
        print("Cache error:", repr(e))

# 3. Kiểm tra toàn bộ ảnh Train
print("\n" + "=" * 60)
print("3. TRAIN IMAGE AUDIT")
print("=" * 60)

train_dir = (
    ROOT / "training/dataset_v2_yolo_split_v2/images/train"
)

images = list(train_dir.glob("*.png"))
images += list(train_dir.glob("*.jpg"))
images += list(train_dir.glob("*.jpeg"))

unreadable = []

print("Total images:", len(images))

for i, path in enumerate(images, 1):
    img = cv2.imread(str(path))

    if img is None:
        unreadable.append(str(path))

    if i % 500 == 0:
        print(f"Checked: {i}/{len(images)}")

print("\nUnreadable images:", len(unreadable))

for path in unreadable[:20]:
    print("  ", path)

print("\nDIAGNOSTIC COMPLETED")
