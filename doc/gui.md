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

### 5. Tab "Xem trước" và Lưới ảnh chụp màn hình (Device Preview Grid)

Cửa sổ chính của ứng dụng sử dụng giao diện phân tab (`ttk.Notebook` theo chủ đề tối) gồm 2 tab: **"Thiết bị"** (toàn bộ tính năng danh sách và điều khiển chi tiết) và **"Xem trước"** (lưới ảnh chụp trực quan).

- **Công tắc Bật xem trước**: Cho phép bật hoặc tắt tính năng xem trước. Mặc định là tắt (`False`) để tiết kiệm tài nguyên CPU, pin và băng thông. Khi tắt, các ô chỉ hiển thị thông tin placeholder và người dùng vẫn có thể bấm nút hoặc nhấp đúp để mở điều khiển scrcpy.
- **Tạm dừng thông minh**: Quá trình chụp preview chỉ chạy khi tab "Xem trước" đang được chọn VÀ công tắc đang bật. Khi chuyển sang tab "Thiết bị" hoặc tắt công tắc, ứng dụng sẽ dừng ngay lập tức vòng chụp và huỷ bỏ các tiến trình chụp đang chạy.
- **Chu kỳ làm mới tuỳ chọn**: Hỗ trợ các mốc chu kỳ làm mới 2s (mặc định), 5s hoặc 10s, được lưu tự động vào cấu hình người dùng.
- **Lưới xem trước tự co giãn**:
  - Tự động sắp xếp số cột phù hợp với chiều ngang cửa sổ và hỗ trợ cuộn dọc mượt mà khi kết nối nhiều thiết bị.
  - Mỗi thiết bị ở trạng thái sẵn sàng (`device`) hiển thị thành một ô thẻ gồm: ảnh chụp màn hình thu nhỏ (lấy qua `adb exec-out screencap -p` và thu nhỏ theo tỷ lệ nguyên bằng `tk.PhotoImage.subsample`), tên máy, serial, chấm trạng thái và huy hiệu "Đang mở" nếu đang có cửa sổ scrcpy điều khiển.
  - Thiết bị `unauthorized` hoặc `offline` hiển thị ô màu xám kèm thông báo trạng thái tương ứng, không thực hiện lệnh chụp.
  - Chụp ảnh song song theo từng thiết bị trong thread pool với timeout 8 giây, có cơ chế bảo vệ tối đa 1 lệnh chụp đang chạy trên mỗi thiết bị nhằm tránh chồng chéo lệnh adb.
  - Lỗi chụp của một thiết bị được cách ly hoàn toàn, không ảnh hưởng thiết bị khác; ô thẻ của thiết bị đó sẽ hiển thị thông báo lỗi ngắn và giữ lại ảnh chụp cũ.
  - **Nhấp đúp vào ô thẻ hoặc bấm "Mở scrcpy"**: Mở cửa sổ điều khiển scrcpy tương ứng với cấu hình đã cài đặt (nếu máy đã mở cửa sổ trước đó thì không mở thêm).

### 6. Chế độ "Xếp lưới live" (Live Tiling)

- Nút **"Xếp lưới live"** / **"Đóng lưới live"**: Tự động mở đồng thời cho tất cả thiết bị đang sẵn sàng (`device`) một cửa sổ scrcpy nhỏ chỉ xem (chế độ `--no-control --no-audio --window-borderless --max-size 360 --max-fps 10 --video-bit-rate 1M`).
- Các cửa sổ live được tính toán toạ độ và kích thước để xếp dạng bàn cờ theo kích thước màn hình máy tính (`winfo_screenwidth/height`).
- Phiên live được quản lý tách biệt độc lập với phiên điều khiển, không ghi đè hay chặn phiên điều khiển của cùng thiết bị.
- Bấm **"Đóng lưới live"** hoặc khi đóng ứng dụng sẽ tự động tắt toàn bộ các cửa sổ live.

### 7. Tuỳ chọn cấu hình scrcpy

Các tuỳ chọn được tự động lưu vào `~/.config/scrcpy-gui/settings.json` (tôn trọng biến môi trường `XDG_CONFIG_HOME`) và áp dụng cho các lần mở thiết bị tiếp theo:

| Tuỳ chọn | Mô tả | Tham số scrcpy / cài đặt tương ứng |
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
| **Bật xem trước** | Bật chụp và hiển thị ảnh thu nhỏ định kỳ ở tab Xem trước (mặc định: tắt) | Cài đặt `preview_enabled` |
| **Chu kỳ làm mới** | Khoảng thời gian chụp lại xem trước: 2s (mặc định) / 5s / 10s | Cài đặt `preview_interval` |

Nếu tệp cấu hình bị hỏng, ứng dụng tự động khôi phục về cài đặt mặc định mà không bị gián đoạn hoạt động.

### 8. Biến môi trường hỗ trợ

- `ADB`: Đường dẫn tệp thực thi `adb`.
- `SCRCPY_BIN`: Đường dẫn tệp thực thi `scrcpy`.
- `SCRCPY_SERVER_PATH`: Đường dẫn tệp `scrcpy-server` (được truyền nguyên vẹn sang cho scrcpy khi khởi chạy).
- `XDG_CONFIG_HOME`: Thư mục lưu cấu hình người dùng (mặc định `~/.config`).

## Build bộ cài

Để tạo gói cài đặt `.deb` (`scrcpy-gui_<version>_amd64.deb`) cho Ubuntu (24.04 / 22.04 x86_64), cần chuẩn bị môi trường và thực hiện các bước sau:

### 1. Cài đặt các gói phụ thuộc hệ thống (APT)

Cài đặt các gói phụ thuộc cho client tĩnh theo cấu hình job `build-linux-x86_64` trong `.github/workflows/release.yml`:

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
    libpipewire-0.3-dev libwayland-dev libdecor-0-dev liburing-dev
```

Ngoài danh sách trên trong workflow, cần cài đặt thêm các công cụ bổ sung để build scrcpy-server và chạy/đóng gói GUI:

```bash
sudo apt install -y openjdk-17-jdk python3 python3-tk
```

> **Lưu ý**: Công cụ đóng gói `dpkg-deb` thuộc gói `dpkg` (đã có sẵn trên các bản phân phối Ubuntu/Debian).

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

