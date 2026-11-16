
# YOLO11n - Fall Detection Training

## 1. Giới thiệu

Thư mục này chứa mã nguồn và tài liệu phục vụ quá trình chuẩn bị dữ liệu, huấn luyện và đánh giá mô hình YOLO11n cho hệ thống giám sát người té ngã (Fall Detection System).

Mô hình được xây dựng nhằm phát hiện và phân loại trạng thái của con người thông qua hình ảnh camera.

## 2. Công nghệ sử dụng

- Python 3.13.5
- Ultralytics YOLO11n
- PyTorch 2.6.0
- OpenCV
- CUDA 11.8
- GPU NVIDIA RTX 3050 Laptop 4GB

## 3. Phân loại đối tượng

Mô hình sử dụng 2 lớp:

| Class ID | Class Name | Ý nghĩa |
|---|---|---|
| 0 | Fallen | Người đã té ngã |
| 1 | Non-fallen | Người không té ngã |

## 4. Dataset

Dataset được tổ chức theo định dạng YOLO Detection.

Đường dẫn dataset:

`training/dataset_v2_yolo_split_v2/`

Cấu trúc:

```text
dataset_v2_yolo_split_v2/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
└── data.yaml
```

### Thống kê dữ liệu

| Tập dữ liệu | Số lượng ảnh |
|---|---:|
| Train | 3,808 |
| Validation | 416 |
| Test | 499 |
| Tổng | 4,723 |

Dataset có hai lớp Fallen và Non-fallen. Một số ảnh không có đối tượng được gán nhãn cũng được giữ lại để hỗ trợ quá trình huấn luyện.

## 5. Quá trình huấn luyện

Mô hình sử dụng YOLO11n với trọng số pretrained ban đầu.

Các thông tin của lần huấn luyện gần nhất:

| Thông số | Giá trị |
|---|---|
| Model | YOLO11n |
| Epochs | 70 |
| GPU | NVIDIA RTX 3050 Laptop 4GB |
| PyTorch | 2.6.0+cu118 |
| Ultralytics | 8.4.207 |
| Thời gian huấn luyện | Khoảng 4.854 giờ |

### Các bước thực hiện

1. Chuẩn bị dataset theo định dạng YOLO.
2. Chia dữ liệu thành Train, Validation và Test.
3. Kiểm tra cấu trúc dataset và nhãn.
4. Sử dụng pretrained weights YOLO11n.
5. Huấn luyện mô hình trên tập Train.
6. Đánh giá mô hình trên tập Validation và Test.
7. Lưu lại trọng số tốt nhất.

## 6. Kết quả huấn luyện

Sau quá trình huấn luyện, mô hình tạo ra các checkpoint:

- `best.pt`: Trọng số có kết quả tốt nhất trong quá trình huấn luyện.
- `last.pt`: Trọng số tại epoch cuối cùng.
- `epoch*.pt`: Các checkpoint tại những epoch tương ứng.

Model tốt nhất được lưu tại:

```text
training/results/
└── fall_detection_yolo11n_v1/
    └── weights/
        └── best.pt
```

Đây là model được sử dụng trong hệ thống phát hiện té ngã.

## 7. Đánh giá mô hình

Mô hình được đánh giá bằng các chỉ số:

- Precision
- Recall
- mAP@50
- mAP@50-95

Các chỉ số này được sử dụng để đánh giá khả năng phát hiện và phân loại đối tượng của mô hình.

## 8. Tích hợp vào hệ thống

Sau khi huấn luyện, file `best.pt` được sử dụng trong chương trình Python để:

1. Nhận luồng hình ảnh từ camera.
2. Thực hiện nhận diện bằng YOLO11n.
3. Phân loại trạng thái Fallen và Non-fallen.
4. Kết hợp cơ chế xác nhận té ngã theo thời gian.
5. Gửi sự kiện cảnh báo đến Backend thông qua MQTT.

## 9. Lưu ý

- Dataset và model weights không được lưu trực tiếp trên GitHub do dung lượng lớn.
- File `best.pt` cần được giữ lại để chạy hệ thống.
- Khi huấn luyện lại, cần cập nhật đường dẫn model và kết quả tương ứng.
- Cần cài đặt PyTorch phù hợp với cấu hình CPU/GPU trước khi chạy các script huấn luyện.
