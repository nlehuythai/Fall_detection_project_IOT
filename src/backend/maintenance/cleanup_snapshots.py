
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Đưa thư mục gốc dự án vào Python path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.db import SessionLocal
from src.backend.models import FallEvent


# =========================
# CONFIGURATION
# =========================

SNAPSHOT_ROOT = PROJECT_ROOT / "data" / "snapshots"

RETENTION_DAYS = 90
MAX_STORAGE_GB = 5
MAX_STORAGE_BYTES = MAX_STORAGE_GB * 1024 ** 3


def get_snapshot_files():
    """Lấy danh sách ảnh JPG trong thư mục snapshots."""
    if not SNAPSHOT_ROOT.exists():
        print("[CLEANUP] Snapshot directory does not exist.")
        return []

    files = []

    for path in SNAPSHOT_ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg"):
            try:
                files.append({
                    "path": path,
                    "key": path.relative_to(SNAPSHOT_ROOT).as_posix(),
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                })
            except OSError as error:
                print(f"[WARNING] Cannot read {path}: {error}")

    return files


def delete_snapshot(db, item):
    """Xóa ảnh và cập nhật snapshot_key trong database."""
    path = item["path"]
    key = item["key"]

    try:
        # Cập nhật database trước khi xóa file
        db.query(FallEvent).filter(
            FallEvent.snapshot_key.in_([
                key,
                key.replace("/", "\\")
            ])
        ).update(
            {FallEvent.snapshot_key: None},
            synchronize_session=False
        )

        db.commit()

        # Xóa ảnh vật lý
        path.unlink()

        print(f"[DELETED] {key}")
        return item["size"]

    except Exception as error:
        db.rollback()
        print(f"[ERROR] Cannot delete {key}: {error}")
        return 0


def cleanup_snapshots():
    print("=" * 50)
    print("[CLEANUP] Starting snapshot cleanup")
    print("=" * 50)

    db = SessionLocal()

    try:
        files = get_snapshot_files()

        if not files:
            print("[CLEANUP] No snapshot files found.")
            return

        total_before = sum(item["size"] for item in files)

        print(f"[INFO] Total images: {len(files)}")
        print(f"[INFO] Current storage: {total_before / 1024**3:.3f} GB")

        now = datetime.now().timestamp()
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).timestamp()

        # Bước 1: Chọn ảnh quá thời hạn lưu trữ
        expired_files = [
            item for item in files
            if item["modified"] < cutoff
        ]

        expired_paths = {item["path"] for item in expired_files}

        # Bước 2: Tính dung lượng còn lại sau khi xóa ảnh quá hạn
        remaining_files = [
            item for item in files
            if item["path"] not in expired_paths
        ]

        remaining_size = sum(item["size"] for item in remaining_files)

        # Bước 3: Nếu vẫn vượt 5 GB, xóa ảnh cũ nhất trước
        excess_files = []

        if remaining_size > MAX_STORAGE_BYTES:
            remaining_files.sort(key=lambda item: item["modified"])

            for item in remaining_files:
                if remaining_size <= MAX_STORAGE_BYTES:
                    break

                excess_files.append(item)
                remaining_size -= item["size"]

        # Bước 4: Xóa các ảnh đã chọn
        files_to_delete = expired_files + excess_files

        deleted_count = 0
        freed_bytes = 0

        for item in files_to_delete:
            freed = delete_snapshot(db, item)

            if freed > 0:
                deleted_count += 1
                freed_bytes += freed

        print("=" * 50)
        print("[CLEANUP] Completed")
        print(f"[RESULT] Deleted images: {deleted_count}")
        print(f"[RESULT] Freed storage: {freed_bytes / 1024**2:.2f} MB")
        print(
            f"[RESULT] Remaining storage (estimated): "
            f"{max(total_before - freed_bytes, 0) / 1024**3:.3f} GB"
        )
        print("=" * 50)

    finally:
        db.close()


if __name__ == "__main__":
    cleanup_snapshots()
