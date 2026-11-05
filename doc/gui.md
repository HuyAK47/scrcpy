# GUI Launcher

`scrcpy-gui` là ứng dụng giao diện đồ hoạ cho scrcpy được viết bằng Python 3 và Tkinter (chỉ sử dụng thư viện chuẩn của Python), với giao diện tiếng Việt. Ứng dụng giúp hiển thị danh sách thiết bị Android đang kết nối adb (cả USB lẫn Wi-Fi), cho phép người dùng mở hoặc dừng cửa sổ scrcpy cho từng thiết bị dễ dàng, quản lý kết nối không dây và lưu cấu hình tuỳ chọn.

## Yêu cầu hệ thống

- Python >= 3.10
- Gói `python3-tk` (trên Ubuntu / Debian: `sudo apt install python3-tk`)
- `adb` và `scrcpy` có sẵn trong `PATH` (hoặc thông qua biến môi trường `ADB` / `SCRCPY_BIN`)

## Cách chạy

Từ thư mục gốc dự án:

```bash
cd gui && python3 -m scrcpy_gui
```

Hoặc chạy trực tiếp từ thư mục gốc với `PYTHONPATH`:

```bash
PYTHONPATH=gui python3 -m scrcpy_gui
```

## Các tính năng chính

### 1. Tìm kiếm binary tự động

Ứng dụng tự động tìm đường dẫn của `adb` và `scrcpy` theo thứ tự ưu tiên:
1. Biến môi trường `SCRCPY_BIN` hoặc `ADB`
2. Cùng thư mục cài đặt (thư mục cha của package khi đóng gói, ví dụ `/opt/scrcpy-gui/scrcpy`, `/opt/scrcpy-gui/adb`)
3. Thư mục trong biến môi trường `PATH`

Nếu không tìm thấy, giao diện hiển thị thông báo cảnh báo rõ ràng mà không gây crash ứng dụng.

### 2. Quản lý danh sách thiết bị

- Chạy `adb devices -l` ngầm và tự động cập nhật mỗi 3 giây trong thread nền (hoặc bấm nút **Làm mới**).
- Phân loại kết nối:
  - **Wi-Fi**: Khi serial có dạng `host:port` hoặc `_adb-tls-connect._tcp`.
  - **USB**: Các kết nối có dây thông thường.
- Hiển thị thông tin trực quan: Tên máy (model chuẩn hoá), Serial, Loại kết nối (USB / Wi-Fi), Trạng thái (Sẵn sàng / Chưa cho phép / Offline / Đang hiển thị).
- Chỉ cho phép bấm **Hiển thị** đối với thiết bị ở trạng thái sẵn sàng (`device`).

### 3. Hiển thị / Dừng cửa sổ mirroring

- Nút **Hiển thị** khởi chạy `scrcpy` với tiêu đề cửa sổ dạng `"<model> (<serial>)"` cùng các tuỳ chọn đã cấu hình.
- Có thể double-click vào dòng thiết bị trong danh sách để mở nhanh màn hình.
- Cho phép mở nhiều thiết bị cùng lúc.
- Nút **Dừng** ngắt tiến trình scrcpy tương ứng với thiết bị được chọn.
- Tự động phát hiện khi cửa sổ scrcpy bị đóng hoặc cáp bị rút: nếu tiến trình kết thúc với mã lỗi, app sẽ hiển thị các dòng `stderr` cuối cùng để thông báo lỗi cho người dùng.
- Khi đóng ứng dụng, app sẽ hỏi xác nhận người dùng có muốn tắt tất cả các cửa sổ scrcpy đang mở hay không.

### 4. Kết nối và chuyển đổi Wi-Fi

- **Kết nối Wi-Fi**: Nhập địa chỉ `IP:port` (mặc định cổng 5555 nếu không ghi cổng) và bấm **Kết nối** (`adb connect`).
- **Ngắt kết nối**: Bấm nút **Ngắt kết nối** cho thiết bị Wi-Fi đang chọn (`adb disconnect <serial>`).
- **Chuyển sang Wi-Fi**: Đối với thiết bị USB đang cắm, bấm **Chuyển sang Wi-Fi** để tự động:
  1. Lấy địa chỉ IP mạng nội bộ của thiết bị qua `adb shell ip route` (giao diện `wlan`).
  2. Kích hoạt chế độ TCP/IP trên cổng 5555 (`adb tcpip 5555`).
  3. Kết nối tự động tới `<ip>:5555` qua Wi-Fi.

Tất cả các lệnh adb đều chạy bất đồng bộ trong thread nền với timeout 10 giây, hiển thị tiến độ và kết quả trên thanh trạng thái.

### 5. Tuỳ chọn cấu hình scrcpy

Các tuỳ chọn được tự động lưu vào `~/.config/scrcpy-gui/settings.json` (tôn trọng biến môi trường `XDG_CONFIG_HOME`) và áp dụng cho các lần mở thiết bị tiếp theo:

| Tuỳ chọn | Mô tả | Tham số scrcpy tương ứng |
|---|---|---|
| **Độ phân giải tối đa** | Giới hạn chiều dài/rộng lớn nhất: Không giới hạn / 1920 / 1280 / 1024 / 800 | `--max-size <size>` |
| **Bitrate** | Tốc độ truyền video: 4M / 8M (mặc định) / 16M | `--video-bit-rate <bitrate>` |
| **FPS tối đa** | Giới hạn khung hình: Không giới hạn / 30 / 60 | `--max-fps <fps>` |
| **Tắt âm thanh** | Không truyền âm thanh từ thiết bị | `--no-audio` |
| **Tắt màn hình ĐT** | Tắt màn hình vật lý của điện thoại khi mirroring | `--turn-screen-off` |
| **Giữ máy thức** | Ngăn điện thoại tự động khoá màn hình | `--stay-awake` |
| **Luôn ở trên** | Giữ cửa sổ scrcpy luôn nằm trên các cửa sổ khác | `--always-on-top` |
| **Toàn màn hình** | Mở scrcpy ở chế độ toàn màn hình | `--fullscreen` |
| **Tham số thêm** | Các cờ dòng lệnh scrcpy bổ sung (phân tách qua `shlex.split`) | Tuỳ biến thêm bởi người dùng |

Nếu tệp cấu hình bị hỏng, ứng dụng tự động khôi phục về cài đặt mặc định mà không bị gián đoạn hoạt động.

### 6. Biến môi trường hỗ trợ

- `ADB`: Đường dẫn tệp thực thi `adb`.
- `SCRCPY_BIN`: Đường dẫn tệp thực thi `scrcpy`.
- `SCRCPY_SERVER_PATH`: Đường dẫn tệp `scrcpy-server` (được truyền nguyên vẹn sang cho scrcpy khi khởi chạy).
- `XDG_CONFIG_HOME`: Thư mục lưu cấu hình người dùng (mặc định `~/.config`).

## Build bộ cài

Để tạo gói cài đặt `.deb` (`scrcpy-gui_<version>_amd64.deb`) cho Ubuntu (24.04 / 22.04 x86_64), cần chuẩn bị môi trường và thực hiện các bước sau:

### 1. Cài đặt các gói phụ thuộc hệ thống (APT)

Dựa theo cấu hình job `build-linux-x86_64` trong `.github/workflows/release.yml`:

```bash
sudo apt update
sudo apt install -y meson ninja-build nasm ffmpeg libavcodec-dev \
    libavdevice-dev libavformat-dev libavutil-dev libswresample-dev \
    libusb-1.0-0 libusb-1.0-0-dev libv4l-dev \
    libasound2-dev libpulse-dev \
    libaudio-dev libfribidi-dev libjack-dev libsndio-dev libx11-dev libxext-dev \
    libxrandr-dev libxcursor-dev libxfixes-dev libxi-dev libxss-dev libxtst-dev \
    libxkbcommon-dev libdrm-dev libva-dev libgbm-dev libgl1-mesa-dev libgles2-mesa-dev \
    libegl1-mesa-dev libdbus-1-dev libibus-1.0-dev libudev-dev libthai-dev \
    libpipewire-0.3-dev libwayland-dev libdecor-0-dev liburing-dev \
    openjdk-17-jdk dpkg-deb python3 python3-tk
```

### 2. Thiết lập biến môi trường Android SDK

Để build `scrcpy-server`, cần có Android SDK và thiết lập biến môi trường `ANDROID_HOME`:

```bash
export ANDROID_HOME=/path/to/android-sdk
```

### 3. Thứ tự các lệnh build và đóng gói

Thực hiện tuần tự từ thư mục gốc dự án:

1. **Build scrcpy-server**:
   ```bash
   release/build_server.sh
   ```
   (Tạo ra `release/work/build-server/server/scrcpy-server`)

2. **Build scrcpy tĩnh và adb**:
   ```bash
   release/build_linux.sh x86_64
   ```
   (Tạo ra `release/work/build-linux-x86_64/dist/`)

3. **Đóng gói file cài đặt `.deb`**:
   ```bash
   release/build_linux_gui_deb.sh
   ```
   (Tạo ra file `.deb` tại `release/output/scrcpy-gui_<version>_amd64.deb`)

4. **Cài đặt và kiểm tra gói**:
   ```bash
   sudo apt install ./release/output/scrcpy-gui_*.deb
   ```

