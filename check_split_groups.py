
from pathlib import Path
from collections import defaultdict, Counter
import re

ROOT = Path("training/dataset_v2_yolo")

image_dir = ROOT / "images" / "train"
label_dir = ROOT / "labels" / "train"

groups = defaultdict(lambda: {
    "images": 0,
    "fallen": 0,
    "non_fallen": 0,
    "empty": 0,
    "missing": 0
})

extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

images = [
    p for p in image_dir.iterdir()
    if p.suffix.lower() in extensions
]

for img in images:
    match = re.match(r"split(\d+)_", img.stem, re.I)

    if not match:
        continue

    group = match.group(1)
    label = label_dir / f"{img.stem}.txt"

    groups[group]["images"] += 1

    if not label.exists():
        groups[group]["missing"] += 1
        continue

    content = label.read_text(encoding="utf-8").strip()

    if not content:
        groups[group]["empty"] += 1
        continue

    for line in content.splitlines():
        parts = line.split()

        if len(parts) != 5:
            continue

        try:
            cls = int(parts[0])

            if cls == 0:
                groups[group]["fallen"] += 1
            elif cls == 1:
                groups[group]["non_fallen"] += 1

        except ValueError:
            pass

print("=" * 75)
print("ORIGINAL GROUP DISTRIBUTION")
print("=" * 75)

total = Counter()

for group in sorted(groups, key=lambda x: int(x)):
    g = groups[group]

    print(
        f"split{group:<5} "
        f"Images: {g['images']:<6} "
        f"Fallen: {g['fallen']:<6} "
        f"Non-fallen: {g['non_fallen']:<6} "
        f"Empty: {g['empty']:<5} "
        f"Missing: {g['missing']}"
    )

    for key in ["images", "fallen", "non_fallen", "empty", "missing"]:
        total[key] += g[key]

print("-" * 75)
print("TOTAL:", dict(total))
