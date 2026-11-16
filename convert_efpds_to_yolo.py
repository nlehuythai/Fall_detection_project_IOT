
from pathlib import Path
from collections import Counter
from PIL import Image
import shutil

ROOT = Path("training/dataset_v2")
OUTPUT = Path("training/dataset_v2_yolo")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# E-FPDS: class 1 = Fallen, class -1 = Non-fallen
CLASS_MAPPING = {
    1: 0,
    -1: 1
}

images = [
    p for p in ROOT.rglob("*")
    if p.is_file() and p.suffix.lower() in IMAGE_EXTS
]

if not images:
    raise RuntimeError(f"Không tìm thấy ảnh trong {ROOT.resolve()}")

image_out = OUTPUT / "images" / "train"
label_out = OUTPUT / "labels" / "train"

image_out.mkdir(parents=True, exist_ok=True)
label_out.mkdir(parents=True, exist_ok=True)

stats = Counter()
errors = []

print("=" * 60)
print("E-FPDS TO YOLO CONVERSION")
print("=" * 60)
print("Total images:", len(images))

for index, img_path in enumerate(images, 1):
    label_path = img_path.with_suffix(".txt")

    if not label_path.exists():
        errors.append((img_path.name, "Missing label"))
        continue

    try:
        with Image.open(img_path) as img:
            width, height = img.size

        content = label_path.read_text(
            encoding="utf-8",
            errors="ignore"
        ).strip()

        converted_lines = []

        if content:
            for line_number, line in enumerate(content.splitlines(), 1):
                parts = line.split()

                if len(parts) != 5:
                    raise ValueError(
                        f"Label field count != 5 at line {line_number}"
                    )

                cls = int(parts[0])
                x1, x2, y1, y2 = map(float, parts[1:])

                if cls not in CLASS_MAPPING:
                    raise ValueError(f"Unknown class ID: {cls}")

                if not (
                    0 <= x1 < x2 <= width
                    and 0 <= y1 < y2 <= height
                ):
                    raise ValueError(
                        f"Invalid bbox: {(x1, x2, y1, y2)}, "
                        f"image size: {(width, height)}"
                    )

                # Pixel coordinates -> YOLO normalized coordinates
                x_center = ((x1 + x2) / 2) / width
                y_center = ((y1 + y2) / 2) / height
                box_width = (x2 - x1) / width
                box_height = (y2 - y1) / height

                new_cls = CLASS_MAPPING[cls]

                converted_lines.append(
                    f"{new_cls} "
                    f"{x_center:.6f} "
                    f"{y_center:.6f} "
                    f"{box_width:.6f} "
                    f"{box_height:.6f}"
                )

                stats[f"class_{new_cls}"] += 1

        # Copy image and write converted label
        shutil.copy2(
            img_path,
            image_out / img_path.name
        )

        (label_out / f"{img_path.stem}.txt").write_text(
            "\n".join(converted_lines),
            encoding="utf-8"
        )

        if not converted_lines:
            stats["empty_labels"] += 1

        stats["converted_images"] += 1

    except Exception as e:
        errors.append((img_path.name, str(e)))

    if index % 500 == 0:
        print(f"Processed {index}/{len(images)} images")

print("\n" + "=" * 60)
print("CONVERSION SUMMARY")
print("=" * 60)

print("Converted images:", stats["converted_images"])
print("Fallen boxes (class 0):", stats["class_0"])
print("Non-fallen boxes (class 1):", stats["class_1"])
print("Empty labels:", stats["empty_labels"])
print("Errors:", len(errors))

if errors:
    print("\nFirst 20 errors:")
    for item in errors[:20]:
        print(item)

print("\nOutput:", OUTPUT.resolve())
print("CONVERSION FINISHED")
