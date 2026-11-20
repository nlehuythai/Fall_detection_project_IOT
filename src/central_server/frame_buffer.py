import cv2
import threading


class FrameBuffer:
    def __init__(self, jpeg_quality=80):
        self.jpeg_quality = jpeg_quality

        # Đồng bộ dữ liệu giữa AI thread và Live View thread
        self.condition = threading.Condition()

        # Chỉ lưu frame mới nhất
        self.latest_frame = None
        self.frame_id = 0

    def update(self, frame):
        """
        Nhận frame từ CameraSession,
        mã hóa JPEG và cập nhật frame mới nhất.
        """

        if frame is None:
            return False

        success, encoded_frame = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )

        if not success:
            return False

        jpeg_bytes = encoded_frame.tobytes()

        with self.condition:
            self.latest_frame = jpeg_bytes
            self.frame_id += 1

            # Thông báo cho các client đang chờ frame mới
            self.condition.notify_all()

        return True

    def get_latest_frame(self, last_frame_id=-1, timeout=1.0):
        """
        Lấy frame mới nhất.

        Nếu chưa có frame mới, chờ tối đa timeout giây.

        Trả về:
            (frame_id, jpeg_bytes)
        """

        with self.condition:
            self.condition.wait_for(
                lambda: (
                    self.latest_frame is not None
                    and self.frame_id != last_frame_id
                ),
                timeout=timeout
            )

            if self.latest_frame is None:
                return None

            if self.frame_id == last_frame_id:
                return None

            return self.frame_id, self.latest_frame