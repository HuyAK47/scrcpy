# Quyết định Thiết kế Giao diện scrcpy-gui

## 1. Bối cảnh và Mục tiêu
Giao diện Tkinter ban đầu của `scrcpy-gui` sử dụng các widget ttk mặc định, mang lại trải nghiệm thị giác thô và lỗi thời. Mục tiêu của đợt tái thiết kế này là nâng cấp lớp hiển thị (view layer) sang phong cách công nghệ hiện đại, chuyên nghiệp, hỗ trợ chủ đề tối làm mặc định và đồng bộ với ngôn ngữ thị giác của biểu tượng Gothic kính màu mới (`app-icon.png`).

## 2. Kiến trúc và Phân tách Trách nhiệm
- **Tách riêng module giao diện:** Toàn bộ bảng màu, phông chữ, thành phần thẻ (card) và chấm trạng thái được đóng gói trong `gui/scrcpy_gui/theme.py`.
- **Bảo toàn tầng logic nghiệp vụ:** Không sửa đổi các module cốt lõi `adb.py`, `launcher.py`, `settings.py` và `binaries.py`.
- **Giữ nguyên định danh cửa sổ và icon:** Giữ nguyên hằng số `WM_CLASS_NAME = "scrcpy-gui"` và hàm `set_window_icon(root)` theo yêu cầu tương thích với tệp `.desktop` và hệ thống X11/Wayland.
- **Ngôn ngữ:** Giữ nguyên 100% tiếng Việt cho toàn bộ nhãn, thông báo và tiêu đề.

## 3. Không thêm Phụ thuộc Môi trường chạy (Zero Runtime Dependencies)
- **Quyết định:** Không sử dụng thư viện ngoài qua pip (như `customtkinter`) để đảm bảo gói `.deb` chỉ phụ thuộc tối thiểu vào `python3 (>= 3.10), python3-tk`.
- **Cơ chế:** Xây dựng trực tiếp trên theme engine `clam` sẵn có của ttk kết hợp với cấu hình Tk option database và vẽ canvas/PhotoImage chuẩn.
- **Tài nguyên ảnh trạng thái:** Các chấm trạng thái được kết xuất dưới dạng tệp PNG 16x16 siêu nhẹ vào `gui/scrcpy_gui/assets/` (`dot-online.png`, `dot-running.png`, `dot-unauthorized.png`, `dot-offline.png`), được script `release/build_linux_gui_deb.sh` tự động sao chép qua lệnh `cp -a`. Đồng thời, module `theme.py` có hàm dự phòng tự vẽ chấm tròn động qua `tk.PhotoImage` nếu tệp ảnh bị thiếu.

## 4. Hệ thống Bảng màu Công nghệ Tối (Dark Tech Palette)
Lấy cảm hứng từ sắc xanh lam thẫm, vàng kim và đỏ thẫm của biểu tượng Gothic:
- **Nền cửa sổ chính (`BG_DARK`):** `#0f141c` (Midnight Navy / xám đen sâu thẳm).
- **Nền thẻ nổi (`BG_CARD`):** `#161d27` (Dark Slate Navy) với viền mảnh `#273244`.
- **Văn bản:**
  - Chính (`TEXT_PRIMARY`): `#f8fafc` (trắng ngà sắc nét).
  - Phụ / Nhãn (`TEXT_SECONDARY`): `#94a3b8` (slate sáng).
  - Mờ / Gợi ý (`TEXT_MUTED`): `#64748b`.
- **Màu nhấn (Accent / Nút Hiển thị):** `#1f6feb`, hover `#388bfd`, pressed `#1158c7`.
- **Nút Dừng (Danger):** `#dc2626`, hover `#ef4444`, pressed `#b91c1c`.
- **Nút phụ (Secondary):** `#222b3a`, viền `#334155`, hover `#2d3748`.
- **Chấm trạng thái thiết bị:**
  - `online` / `device`: `#10b981` (Xanh ngọc lục bảo).
  - `running` (đang hiển thị): `#38bdf8` (Xanh da trời công nghệ).
  - `unauthorized`: `#f59e0b` (Vàng kim Gothic).
  - `offline`: `#ef4444` (Đỏ san hô).
- **Hộp cảnh báo (Banner):** Nền `#2b1e09`, viền `#d97706`, chữ `#fef08a`.

## 5. Bố cục dạng Thẻ (Card Layout) và Thành phần Giao diện
1. **Thẻ Kết nối Wi-Fi:** Bố cục hàng ngang tinh gọn với ô nhập IP/cổng (phông monospace), nút Kết nối, Chuyển sang Wi-Fi và Ngắt kết nối.
2. **Thẻ Danh sách Thiết bị:**
   - Thanh tiêu đề hiển thị tên thẻ, phụ đề hướng dẫn và huy hiệu số lượng thiết bị (badge `BADGE_BG` `#1e293b`).
   - Bảng Treeview cao 32px mỗi dòng (thoáng đãng), cột `#0` hiển thị chấm trạng thái màu trực quan.
   - Tô màu dòng trạng thái bằng Treeview tags (`running`, `unauthorized`, `offline`).
   - Dòng nhắc nhẹ nhàng khi chưa có thiết bị kết nối.
   - Nút hành động nổi bật với biểu tượng ký tự Unicode (`▶  Hiển thị`, `■  Dừng`, `⟳  Làm mới`).
3. **Thẻ Tuỳ chọn Scrcpy:**
   - Nhóm 3 ô chọn độ phân giải, bitrate, FPS tối đa.
   - Nhóm 5 hộp kiểm tính năng (tắt âm thanh, tắt màn hình, giữ máy thức, luôn ở trên, toàn màn hình).
   - Ô nhập tham số mở rộng.
4. **Thanh trạng thái chân trang:**
   - Dấu chấm trạng thái trực quan bên trái (`● Sẵn sàng`, thông báo quét, thông báo lỗi).
   - Đường dẫn thực thi binary `adb` và `scrcpy` bên phải dạng chữ đơn khoảng.

## 6. Phông chữ Hệ thống và Phân cấp Chữ
Tự động dò tìm phông chữ sans-serif chất lượng cao theo thứ tự ưu tiên:
`Inter` ➔ `Ubuntu` ➔ `DejaVu Sans` ➔ `Liberation Sans` ➔ `Segoe UI` ➔ `sans-serif`.
Đối với dữ liệu kỹ thuật (địa chỉ IP, serial, đường dẫn binary), sử dụng phông monospace:
`DejaVu Sans Mono` ➔ `Liberation Mono` ➔ `Ubuntu Mono` ➔ `monospace`.
