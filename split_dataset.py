
from pathlib import Path
from collections import Counter
import shutil
import re

SOURCE = Path("training/dataset_v2_yolo")
OUTPUT = Path("training/dataset_v2_yolo_split_v2")

IMAGE_DIR = SOURCE / "images" / "train"
LABEL_DIR = SOURCE / "labels" / "train"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Giữ nguyên split10 làm validation
VAL_GROUP = "10"

# Các nhóm hỗn hợp dùng để tạo train và test
MIXED_GROUPS = ["1", "2", "3"]

# Mỗi đoạn gồm 50 frame liên tiếp
CHUNK_SIZE = 50

# Khoảng cách loại bỏ quanh đoạn test để giảm rò rỉ dữ liệu
BUFFER = 5

# split11 chỉ có Fallen nên đưa toàn bộ vào train
FALLEN_ONLY_GROUP = "11"


def get_group_and_index(path):
    match = re.match(
        r"split(\d+)_(\d+)$",
        path.stem,
        re.IGNORECASE
    )

    if not match:
        return None, None

    return match.group(1), int(match.group(2))


def read_classes(label_path):
    classes = set()

    content = label_path.read_text(encoding="utf-8").strip()

    if not content:
        return classes

    for line in content.splitlines():
        parts = line.split()

        if len(parts) != 5:
            raise ValueError(
                f"Nhãn không đúng 5 trường: {label_path.name}"
            )

        cls = int(parts[0])

        if cls not in (0, 1):
            raise ValueError(
                f"Class không hợp lệ trong {label_path.name}: {cls}"
            )

        classes.add(cls)

    return classes


def prepare_output():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Thư mục đích đã tồn tại: {OUTPUT.resolve()}\n"
            "Hãy đổi tên hoặc di chuyển thư mục cũ trước khi chạy."
        )

    for split in ["train", "val", "test"]:
        (OUTPUT / "images" / split).mkdir(
            parents=True,
            exist_ok=True
        )
        (OUTPUT / "labels" / split).mkdir(
            parents=True,
            exist_ok=True
        )


def copy_pair(img, split):
    label = LABEL_DIR / f"{img.stem}.txt"

    if not label.exists():
        raise FileNotFoundError(f"Thiếu label: {label}")

    target_img = OUTPUT / "images" / split / img.name
    target_label = OUTPUT / "labels" / split / label.name

    shutil.copy2(img, target_img)
    shutil.copy2(label, target_label)


def main():
    if not IMAGE_DIR.exists() or not LABEL_DIR.exists():
        raise FileNotFoundError("Không tìm thấy dataset nguồn.")

    images = [
        p for p in IMAGE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]

    # Gom ảnh theo nhóm gốc
    groups = {}

    for img in images:
        group, index = get_group_and_index(img)

        if group is None:
            raise ValueError(f"Tên ảnh không đúng định dạng: {img.name}")

        groups.setdefault(group, []).append((index, img))

    for group in groups:
        groups[group].sort(key=lambda item: item[0])

    expected_groups = set(MIXED_GROUPS + [VAL_GROUP, FALLEN_ONLY_GROUP])

    if set(groups) != expected_groups:
        raise ValueError(
            f"Nhóm dataset không như dự kiến. "
            f"Đang có: {sorted(groups)}"
        )

    # Kiểm tra nhãn và chuẩn bị dữ liệu
    labels = {}

    for img in images:
        label = LABEL_DIR / f"{img.stem}.txt"

        if not label.exists():
            raise FileNotFoundError(f"Thiếu label: {label}")

        labels[img.name] = read_classes(label)

    # Chia các nhóm 1, 2, 3 thành các đoạn liên tiếp
    chunks_by_group = {}

    for group in MIXED_GROUPS:
        items = groups[group]
        chunks = [
            items[i:i + CHUNK_SIZE]
            for i in range(0, len(items), CHUNK_SIZE)
        ]
        chunks_by_group[group] = chunks

    # Chọn cùng một vị trí chunk theo chu kỳ 5.
    # Thử các offset để đảm bảo Test có cả hai lớp.
    selected_offset = None
    test_images = []

    for offset in range(5):
        candidate = []

        for group in MIXED_GROUPS:
            chunks = chunks_by_group[group]

            for chunk_index, chunk in enumerate(chunks):
                if chunk_index % 5 == offset:
                    candidate.extend(img for _, img in chunk)

        candidate_classes = set()

        for img in candidate:
            candidate_classes.update(labels[img.name])

        if candidate_classes == {0, 1}:
            selected_offset = offset
            test_images = candidate
            break

    if selected_offset is None:
        raise RuntimeError(
            "Không tìm được cách chia Test có đủ hai lớp. "
            "Cần kiểm tra lại nhãn và điều chỉnh cách chia."
        )

    test_names = {img.name for img in test_images}

    # Đánh dấu vùng buffer quanh các chunk test
    excluded_names = set()

    for group in MIXED_GROUPS:
        items = groups[group]
        chunks = chunks_by_group[group]

        for chunk_index, chunk in enumerate(chunks):
            if chunk_index % 5 != selected_offset:
                continue

            # Loại bỏ BUFFER ảnh ngay trước và sau chunk test
            first_index = chunk[0][0]
            last_index = chunk[-1][0]

            for frame_index, img in items:
                if (
                    first_index - BUFFER <= frame_index < first_index
                    or last_index < frame_index <= last_index + BUFFER
                ):
                    excluded_names.add(img.name)

    # Xác định tập dữ liệu
    assignments = {}

    for group in MIXED_GROUPS:
        for _, img in groups[group]:
            if img.name in test_names:
                assignments[img.name] = "test"
            elif img.name in excluded_names:
                assignments[img.name] = "discard"
            else:
                assignments[img.name] = "train"

    # Validation: split10
    for _, img in groups[VAL_GROUP]:
        assignments[img.name] = "val"

    # Train: split11
    for _, img in groups[FALLEN_ONLY_GROUP]:
        assignments[img.name] = "train"

    prepare_output()

    # Copy dữ liệu
    for img in images:
        split = assignments[img.name]

        if split == "discard":
            continue

        copy_pair(img, split)

    # Thống kê
    stats = {
        split: {
            "images": 0,
            "boxes": Counter(),
            "empty": 0
        }
        for split in ["train", "val", "test"]
    }

    for img in images:
        split = assignments[img.name]

        if split == "discard":
            continue

        stats[split]["images"] += 1

        classes = labels[img.name]

        if not classes:
            stats[split]["empty"] += 1

        label = LABEL_DIR / f"{img.stem}.txt"

        for line in label.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cls = int(line.split()[0])
                stats[split]["boxes"][cls] += 1

    # Kiểm tra cả hai lớp
    for split in ["train", "val", "test"]:
        present = {
            cls for cls in (0, 1)
            if stats[split]["boxes"][cls] > 0
        }

        if present != {0, 1}:
            raise RuntimeError(
                f"Tập {split} không có đủ hai lớp: {present}"
            )

    # Tạo data.yaml
    yaml_content = """path: .
train: images/train
val: images/val
test: images/test

nc: 2
names:
  0: Fallen
  1: Non-fallen
"""

    (OUTPUT / "data.yaml").write_text(
        yaml_content,
        encoding="utf-8"
    )

    print("=" * 65)
    print("NEW DATASET SPLIT SUMMARY")
    print("=" * 65)

    print("Original images:", len(images))
    print("Selected test chunk offset:", selected_offset)
    print("Discarded buffer images:", len(excluded_names))

    for split in ["train", "val", "test"]:
        s = stats[split]

        print(f"\n[{split.upper()}]")
        print("Images:", s["images"])
        print("Fallen boxes (class 0):", s["boxes"][0])
        print("Non-fallen boxes (class 1):", s["boxes"][1])
        print("Empty labels:", s["empty"])

    copied = sum(stats[s]["images"] for s in stats)

    print("\nTotal copied:", copied)
    print("Total discarded:", len(excluded_names))
    print("Errors: 0")
    print("Output:", OUTPUT.resolve())
    print("YAML:", (OUTPUT / "data.yaml").resolve())
    print("\nSPLITTING COMPLETED")


if __name__ == "__main__":
    main()
