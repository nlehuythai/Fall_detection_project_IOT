# Fall Detection IoT -- Hệ thống phát hiện té ngã sử dụng IoT và AI

Hệ thống giám sát và phát hiện té ngã trong môi trường gia đình, sử dụng
camera ESP32-CAM kết hợp các mô hình thị giác máy tính. Khi phát hiện sự
kiện té ngã, hệ thống lưu sự kiện, cung cấp giao diện quản lý và gửi
cảnh báo đến các thành viên hộ gia đình đã liên kết Telegram.

> **Trạng thái dự án:** Phiên bản hiện tại sử dụng Central AI Server
> chạy cục bộ. Video được xử lý tại máy tính chạy AI Server; hệ thống
> gửi thông tin sự kiện và snapshot qua Backend. Triển khai Cloud là
> định hướng phát triển trong tương lai, chưa phải cấu hình triển khai
> hiện tại.

## Mục lục

-   [1. Giới thiệu](#1-giới-thiệu)
-   [2. Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
-   [3. Chức năng chính](#3-chức-năng-chính)
-   [4. Công nghệ sử dụng](#4-công-nghệ-sử-dụng)
-   [5. Cấu trúc thư mục](#5-cấu-trúc-thư-mục)
-   [6. Yêu cầu môi trường](#6-yêu-cầu-môi-trường)
-   [7. Cài đặt dự án](#7-cài-đặt-dự-án)
-   [8. Cấu hình biến môi trường](#8-cấu-hình-biến-môi-trường)
-   [9. Khởi chạy hệ thống](#9-khởi-chạy-hệ-thống)
-   [10. Quy trình hoạt động](#10-quy-trình-hoạt-động)
-   [11. Lưu ý bảo mật](#11-lưu-ý-bảo-mật)
-   [12. Hạn chế và định hướng phát
    triển](#12-hạn-chế-và-định-hướng-phát-triển)

## 1. Giới thiệu

Fall Detection IoT hướng đến việc hỗ trợ giám sát an toàn cho người thân
trong gia đình. Camera ESP32-CAM truyền luồng video về máy tính chạy
Central AI Server. Tại đây, hệ thống sử dụng mô hình YOLO để phát hiện
và phân loại trạng thái, kết hợp Pose Estimation và phân tích theo thời
gian để đánh giá tình huống té ngã.

Backend chịu trách nhiệm quản lý người dùng, hộ gia đình, camera và sự
kiện. Frontend cung cấp giao diện theo dõi, quản lý camera và xem lại sự
kiện. Telegram Alert Listener tiếp nhận thông báo sự kiện và gửi cảnh
báo đến các tài khoản Telegram đã liên kết với hộ gia đình tương ứng.

Trong kiến trúc hiện tại, video được xử lý tại máy tính trong mạng gia
đình. Không cần tải toàn bộ video liên tục lên Cloud.

## 2. Kiến trúc hệ thống

``` text
ESP32-S3 + OV2640
       |
       | Luồng video MJPEG
       v
Central AI Server
  - CameraManager
  - CameraSession (mỗi camera một session)
  - ModelManager
  - YOLO Detection + Pose Estimation
  - Temporal Fall Analysis
  - FrameBuffer chia sẻ khung hình
       |
       +---------------------------+
       |                           |
       | Sự kiện té ngã / snapshot | Luồng MJPEG Live View
       v                           v
Backend (FastAPI) <----------- Frontend (React)
  - Xác thực người dùng              - Dashboard
  - Quản lý hộ gia đình              - Quản lý camera
  - Quản lý camera                   - Live View
  - Quản lý sự kiện                  - Quản lý sự kiện
  - PostgreSQL                       - Hộ gia đình / hồ sơ
       |
       | Thông báo sự kiện qua MQTT
       v
Telegram Alert Listener
       |
       v
Shared Telegram Bot
       |
       v
Các Telegram chat đã liên kết
```

### Vai trò của từng thành phần

-   **ESP32-CAM:** Thu thập hình ảnh và cung cấp luồng video MJPEG qua
    mạng Wi-Fi.
-   **Central AI Server:** Quản lý kết nối camera, đọc khung hình, chạy
    các mô hình AI và tạo luồng hình ảnh phục vụ Live View.
-   **Backend:** Cung cấp REST API, xác thực, phân quyền hộ gia đình,
    quản lý camera và lưu trữ sự kiện trong PostgreSQL.
-   **Frontend:** Giao diện web để người dùng quản lý hộ gia đình,
    camera, sự kiện và xem Live View.
-   **Telegram Alert Listener:** Lắng nghe thông báo sự kiện và gửi cảnh
    báo đến các Telegram chat đã liên kết.

Frontend không kết nối trực tiếp đến ESP32-CAM. Luồng Live View đi qua
Backend và Central AI Server. CameraSession là thành phần sở hữu kết nối
đọc video từ camera; việc mở hoặc đóng Live View không được dùng để khởi
động hoặc dừng AI Monitoring.

## 3. Chức năng chính

-   Đăng ký, đăng nhập và xác thực API bằng JWT.
-   Quản lý hộ gia đình và thành viên.
-   Quản lý camera và trạng thái hoạt động.
-   Bật/tắt AI Monitoring cho camera.
-   Quản lý tập trung camera thông qua Central AI Server.
-   Phát hiện té ngã bằng YOLO kết hợp Pose Estimation và phân tích theo
    thời gian.
-   Thử kết nối lại camera khi luồng ESP32-CAM bị gián đoạn.
-   Lưu trữ, xem và cập nhật trạng thái xử lý sự kiện té ngã.
-   Live View bằng MJPEG thông qua Backend, có kiểm tra quyền thành viên
    hộ gia đình.
-   Gửi cảnh báo Telegram thông qua shared bot và các tài khoản Telegram
    đã liên kết.

## 4. Công nghệ sử dụng

  -----------------------------------------------------------------------
  Thành phần                          Công nghệ
  ----------------------------------- -----------------------------------
  Camera IoT                          ESP32-S3, OV2640, Wi-Fi

  AI / Computer Vision                Python, PyTorch, Ultralytics YOLO,
                                      OpenCV, Pose Estimation

  AI Server                           FastAPI, CameraManager,
                                      CameraSession, FrameBuffer

  Backend                             FastAPI, SQLAlchemy, Pydantic, JWT

  Cơ sở dữ liệu                       PostgreSQL

  Truyền thông / cảnh báo             MQTT, Paho MQTT, Telegram Bot API

  Frontend                            React, Vite, React Router, Tailwind
                                      CSS, Axios, Recharts
  -----------------------------------------------------------------------

## 5. Cấu trúc thư mục

``` text
Fall_detection_IOT_project/
├── data/                       # Dữ liệu cục bộ; dataset/snapshot có thể không được đưa lên Git
├── docs/                       # Tài liệu dự án
├── firmware/                   # Mã nguồn firmware ESP32
├── frontend/
│   ├── src/
│   │   ├── components/         # Component giao diện, bao gồm LiveView
│   │   ├── contexts/           # AuthContext và HouseholdContext
│   │   ├── layouts/            # Bố cục ứng dụng
│   │   ├── pages/              # Dashboard, Cameras, Events, Household, Profile, Auth
│   │   ├── routes/             # Bảo vệ các route
│   │   └── services/           # Các service gọi Backend API
│   ├── package.json
│   └── vite.config.js
├── src/
│   ├── ai_engine/              # ModelManager và TemporalAnalyzer
│   ├── backend/                # FastAPI Backend, routers, models, schemas, services
│   ├── central_server/         # CameraManager, CameraSession, FrameBuffer, AI API
│   ├── notifications/          # Telegram Alert Listener
│   └── pc/                     # Module xử lý phát hiện và script kiểm thử trên PC
├── tests/                      # Các bài kiểm thử
├── training/                   # Script huấn luyện và kết quả huấn luyện cục bộ
├── .env.example                # Mẫu biến môi trường
├── .gitignore
├── requirements.txt
└── README.md
```

Model weights, dataset, snapshot, file môi trường cá nhân và kết quả
huấn luyện có thể không được lưu trong repository. Người triển khai cần
tự chuẩn bị các tệp cần thiết theo cấu hình dự án.

## 6. Yêu cầu môi trường

-   Windows 10/11 (các lệnh hướng dẫn bên dưới sử dụng Command Prompt).
-   Python 3.13 được khuyến nghị theo môi trường phát triển hiện tại.
-   Node.js và npm tương thích với phiên bản Vite trong
    `frontend/package.json`.
-   PostgreSQL.
-   Git.
-   ESP32-S3 camera đã cấu hình để cung cấp luồng MJPEG.
-   GPU NVIDIA được khuyến nghị để tăng tốc suy luận AI. Có thể cần điều
    chỉnh cấu hình nếu chạy bằng CPU.

### PyTorch và CUDA

Môi trường phát triển hiện tại sử dụng PyTorch `2.6.0` với CUDA 11.8.
Cần cài phiên bản PyTorch phù hợp với GPU, driver và môi trường CUDA của
máy. Lệnh cài CUDA 11.8 được trình bày ở phần cài đặt. Nếu cấu hình máy
khác, hãy chọn lệnh tương ứng từ trang hướng dẫn cài đặt chính thức của
PyTorch.

## 7. Cài đặt dự án

### Bước 1: Clone repository

``` cmd
git clone <YOUR_REPOSITORY_URL>
cd Fall_detection_IOT_project
```

Thay `<YOUR_REPOSITORY_URL>` bằng URL repository GitHub của dự án.

### Bước 2: Tạo và kích hoạt môi trường Python

``` cmd
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
```

### Bước 3: Cài đặt PyTorch

Với môi trường phát triển sử dụng CUDA 11.8:

``` cmd
pip install torch==2.6.0+cu118 torchvision==0.21.0+cu118 torchaudio==2.6.0+cu118 --index-url https://download.pytorch.org/whl/cu118
```

Nếu sử dụng phiên bản CUDA khác hoặc CPU, hãy chọn cấu hình phù hợp từ
trang cài đặt chính thức của PyTorch.

### Bước 4: Cài đặt các thư viện Python

``` cmd
pip install -r requirements.txt
```

### Bước 5: Cài đặt thư viện Frontend

``` cmd
cd frontend
npm install
cd ..
```

### Bước 6: Tạo PostgreSQL database

Tạo database có tên tương ứng với cấu hình trong `.env`. Ví dụ:

``` sql
CREATE DATABASE fall_detection_db;
```

Cập nhật username và password PostgreSQL trong file `.env`.

Lưu ý: Việc tạo database không đồng nghĩa với việc các bảng ứng dụng đã
được tạo. Cần thực hiện quy trình khởi tạo schema hoặc migration theo
cấu hình hiện tại của Backend.

### Bước 7: Tạo file cấu hình môi trường

Tại thư mục gốc:

``` cmd
copy .env.example .env
```

Mở file `.env` và cập nhật các giá trị phù hợp với máy tính, camera,
database và Telegram Bot của bạn.

## 8. Cấu hình biến môi trường

File `.env.example` ở thư mục gốc là mẫu cấu hình. Các biến chính:

  -----------------------------------------------------------------------
  Biến                                Chức năng
  ----------------------------------- -----------------------------------
  `MODEL_PATH`                        Đường dẫn đến model weights phát
                                      hiện té ngã đã huấn luyện

  `ESP32_CAMERA_URL`                  URL luồng MJPEG của ESP32-CAM mặc
                                      định, nếu được sử dụng trong cấu
                                      hình camera

  `TELEGRAM_BOT_TOKEN`                Token của shared Telegram Bot

  `TELEGRAM_BOT_USERNAME`             Username của shared Telegram Bot

  `DB_HOST`                           Địa chỉ PostgreSQL

  `DB_PORT`                           Cổng PostgreSQL

  `DB_NAME`                           Tên database

  `DB_USER`                           Tài khoản PostgreSQL

  `DB_PASSWORD`                       Mật khẩu PostgreSQL

  `JWT_SECRET_KEY`                    Secret dùng để ký access token

  `JWT_ALGORITHM`                     Thuật toán ký JWT

  `ACCESS_TOKEN_EXPIRE_MINUTES`       Thời hạn access token tính bằng
                                      phút

  `BACKEND_API_URL`                   Địa chỉ Backend API được các thành
                                      phần cần thiết sử dụng

  `CENTRAL_AI_API_URL`                Địa chỉ Central AI Server

  `CENTRAL_AI_API_KEY`                Khóa nội bộ xác thực yêu cầu từ
                                      Backend đến Central AI Server
  -----------------------------------------------------------------------

Hãy thay các giá trị mẫu bằng thông tin thực tế. Sử dụng secret đủ mạnh
và riêng biệt cho `JWT_SECRET_KEY` và `CENTRAL_AI_API_KEY`. Không commit
file `.env`, token thật, mật khẩu hoặc API key lên GitHub.

Các biến môi trường thực sự cần thiết phụ thuộc vào service và chức năng
được khởi chạy. Cần giữ `.env.example` đồng bộ với các biến được đọc
trong source code.

## 9. Khởi chạy hệ thống

Khởi chạy từng thành phần trong một cửa sổ Command Prompt riêng. Với các
thành phần Python, kích hoạt môi trường ảo trước khi chạy.

### 9.1. Khởi chạy Backend

Tại thư mục gốc dự án:

``` cmd
.venv\Scripts\activate
uvicorn src.backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Tài liệu API Swagger thường truy cập tại:

``` text
http://127.0.0.1:8000/docs
```

### 9.2. Khởi chạy Central AI Server

Mở cửa sổ CMD khác, tại thư mục gốc:

``` cmd
.venv\Scripts\activate
uvicorn src.central_server.api:app --host 127.0.0.1 --port 8001
```

Central AI Server tải các model AI và quản lý những CameraSession. Đảm
bảo URL và API key nội bộ được cấu hình nhất quán giữa Backend và
Central AI Server.

### 9.3. Khởi chạy Telegram Alert Listener

Mở cửa sổ CMD khác, tại thư mục gốc:

``` cmd
.venv\Scripts\activate
python -m src.notifications.telegram_alert_listener
```

Listener cần cấu hình shared Telegram bot và các thông số MQTT mà source
code đang sử dụng. Kiểm tra broker và topic trong cấu hình trước khi
chạy.

### 9.4. Khởi chạy Frontend

Mở một cửa sổ CMD khác:

``` cmd
cd frontend
npm run dev
```

Vite sẽ hiển thị địa chỉ truy cập Frontend trong terminal (thường là
`http://localhost:5173`).

## 10. Quy trình hoạt động

1.  Đăng ký hoặc cấu hình camera ESP32 trong ứng dụng và gắn camera với
    một hộ gia đình.
2.  Cấu hình URL luồng camera để Central AI Server có thể truy cập
    ESP32-CAM qua mạng nội bộ.
3.  Bật AI Monitoring cho camera từ giao diện ứng dụng.
4.  Central AI Server tạo hoặc khởi chạy CameraSession tương ứng, đọc
    frame và thực hiện pipeline nhận diện.
5.  Pipeline AI phân tích hình ảnh và thông tin theo thời gian để xác
    định khả năng xảy ra té ngã.
6.  Backend lưu trữ và cung cấp sự kiện cho các thành viên hộ gia đình
    có quyền truy cập.
7.  Telegram Alert Listener xử lý thông báo sự kiện và gửi cảnh báo đến
    các Telegram chat đã liên kết.
8.  Thành viên được cấp quyền có thể mở Live View thông qua endpoint
    stream được Backend bảo vệ.

Live View chỉ phục vụ quan sát video, không phải điều kiện để AI xử lý.
Khi người dùng đóng Live View, request nhận video của trình duyệt sẽ kết
thúc; AI Monitoring vẫn tiếp tục hoạt động nếu camera vẫn được bật giám
sát.

## 11. Lưu ý bảo mật

-   Không commit file `.env`, access token, Telegram bot token, mật khẩu
    database hoặc internal API key.
-   Thay toàn bộ secret mẫu trước khi chạy ứng dụng.
-   Chỉ cho phép các thành phần đáng tin cậy truy cập Central AI Server
    và bảo vệ API nội bộ bằng API key đủ mạnh.
-   Không công khai luồng camera hoặc Backend API ra Internet nếu chưa
    có xác thực và bảo vệ truyền tải phù hợp.
-   Backend phải kiểm tra quyền thành viên hộ gia đình trước khi cung
    cấp stream camera, snapshot hoặc dữ liệu sự kiện.
-   Không sử dụng MQTT broker công khai cho dữ liệu nhạy cảm hoặc triển
    khai thực tế nếu chưa đánh giá cơ chế xác thực, phân tách topic và
    kiểm tra nội dung message.
-   Các URL trong hướng dẫn là địa chỉ phát triển cục bộ, không phải cấu
    hình production.

## 12. Hạn chế và định hướng phát triển

-   Cấu hình được mô tả hiện tại là Central AI Server chạy cục bộ, chưa
    phải hệ thống Cloud hoàn chỉnh.
-   Khả năng xử lý nhiều camera phụ thuộc CPU, VRAM, độ phân giải camera
    và cấu hình suy luận. Cần benchmark trên phần cứng triển khai thực
    tế.
-   Cần tiếp tục kiểm thử khả năng tự kết nối lại, quản lý tài nguyên,
    chạy nhiều camera đồng thời và xử lý lỗi.
-   Có thể tiếp tục cải thiện độ chính xác mô hình thông qua dữ liệu
    huấn luyện, đánh giá và tinh chỉnh thuật toán.
-   Định hướng tương lai là triển khai Cloud phù hợp với ngân sách, đồng
    thời duy trì cơ chế phân tách dữ liệu giữa các hộ gia đình.

> **Tuyên bố sử dụng:** Hệ thống là công cụ hỗ trợ giám sát, không đảm
> bảo phát hiện chính xác mọi tình huống té ngã và không thay thế dịch
> vụ cấp cứu, thiết bị y tế hoặc sự giám sát trực tiếp của con người.
