"""Giao diện người dùng Tkinter cho scrcpy-gui."""

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from . import adb
from .binaries import find_adb, find_scrcpy
from .launcher import Launcher
from .settings import (
    BITRATE_OPTIONS,
    MAX_FPS_OPTIONS,
    MAX_SIZE_OPTIONS,
    Settings,
    load_settings,
    save_settings,
)


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSETS_DIR / "app-icon.png"
# Lớp cửa sổ (WM_CLASS) khớp StartupWMClass trong scrcpy-gui.desktop
WM_CLASS_NAME = "scrcpy-gui"


def set_window_icon(root: tk.Tk, icon_path: Path = APP_ICON_PATH) -> bool:
    """Đặt icon cho cửa sổ ứng dụng. Trả về False nếu không nạp được ảnh."""
    if not icon_path.is_file():
        return False
    try:
        image = tk.PhotoImage(file=str(icon_path))
        root.iconphoto(True, image)
    except tk.TclError:
        return False
    # Giữ tham chiếu để ảnh không bị thu hồi bộ nhớ
    root._app_icon = image  # type: ignore[attr-defined]
    return True


class ScrcpyApp:
    """Ứng dụng giao diện chính."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("scrcpy GUI - Điều khiển thiết bị Android")
        self.root.geometry("820x680")
        self.root.minsize(720, 560)

        # Trạng thái binary
        self.adb_bin = find_adb()
        self.scrcpy_bin = find_scrcpy()

        # Quản lý tiến trình & cài đặt
        self.launcher = Launcher(scrcpy_bin=self.scrcpy_bin)
        self.settings: Settings = load_settings()

        # Bộ nhớ thiết bị hiện tại {serial: DeviceInfo}
        self.devices_by_serial: Dict[str, adb.DeviceInfo] = {}
        self._refreshing = False
        self._closing = False

        self._init_ui()
        self._init_timer()

        # Xử lý sự kiện đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _init_ui(self) -> None:
        """Khởi tạo bố cục giao diện."""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Cảnh báo nếu thiếu binary
        self._init_banner(main_frame)

        # 2. Khung kết nối Wi-Fi
        self._init_wifi_frame(main_frame)

        # 3. Khung danh sách thiết bị
        self._init_device_list_frame(main_frame)

        # 4. Khung tuỳ chọn cấu hình
        self._init_settings_frame(main_frame)

        # 5. Thanh trạng thái dưới đáy
        self._init_status_bar()

    def _init_banner(self, parent: ttk.Frame) -> None:
        """Hiển thị cảnh báo nếu không tìm thấy adb hoặc scrcpy."""
        missing = []
        if not self.adb_bin:
            missing.append("adb")
        if not self.scrcpy_bin:
            missing.append("scrcpy")

        if missing:
            msg = (
                f"Cảnh báo: Không tìm thấy lệnh thực thi '{', '.join(missing)}'.\n"
                "Vui lòng đảm bảo các công cụ đã được cài đặt trong PATH hoặc qua biến môi trường ADB / SCRCPY_BIN."
            )
            banner = tk.Label(
                parent,
                text=msg,
                bg="#fff3cd",
                fg="#856404",
                padx=10,
                pady=6,
                justify=tk.LEFT,
                relief=tk.SOLID,
                borderwidth=1,
            )
            banner.pack(fill=tk.X, pady=(0, 10))

    def _init_wifi_frame(self, parent: ttk.Frame) -> None:
        """Khu vực kết nối mạng Wi-Fi."""
        frame = ttk.LabelFrame(parent, text="Kết nối Wi-Fi", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="Địa chỉ IP[:cổng]:").pack(side=tk.LEFT, padx=(0, 6))

        self.wifi_ip_var = tk.StringVar(value="")
        self.wifi_entry = ttk.Entry(frame, textvariable=self.wifi_ip_var, width=22)
        self.wifi_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.wifi_entry.bind("<Return>", lambda e: self._on_connect_wifi_click())

        self.btn_connect = ttk.Button(
            frame,
            text="Kết nối",
            command=self._on_connect_wifi_click,
        )
        self.btn_connect.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_switch_wifi = ttk.Button(
            frame,
            text="Chuyển sang Wi-Fi",
            command=self._on_switch_wifi_click,
            state=tk.DISABLED,
        )
        self.btn_switch_wifi.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_disconnect = ttk.Button(
            frame,
            text="Ngắt kết nối",
            command=self._on_disconnect_wifi_click,
            state=tk.DISABLED,
        )
        self.btn_disconnect.pack(side=tk.LEFT, padx=(0, 6))

    def _init_device_list_frame(self, parent: ttk.Frame) -> None:
        """Danh sách thiết bị kết nối."""
        frame = ttk.LabelFrame(parent, text="Danh sách thiết bị", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Treeview + Scrollbar
        tree_container = ttk.Frame(frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("model", "serial", "transport", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=6,
        )

        self.tree.heading("model", text="Tên máy")
        self.tree.heading("serial", text="Serial")
        self.tree.heading("transport", text="Kết nối")
        self.tree.heading("status", text="Trạng thái")

        self.tree.column("model", width=200, minwidth=140, stretch=True)
        self.tree.column("serial", width=190, minwidth=140, stretch=False)
        self.tree.column("transport", width=90, minwidth=80, stretch=False, anchor=tk.CENTER)
        self.tree.column("status", width=220, minwidth=160, stretch=False)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_device_selected)
        self.tree.bind("<Double-1>", self._on_device_double_click)

        # Nút điều khiển
        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill=tk.X, pady=(8, 0))

        self.btn_start = ttk.Button(
            btn_bar,
            text="Hiển thị",
            command=self._on_start_click,
            state=tk.DISABLED,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_stop = ttk.Button(
            btn_bar,
            text="Dừng",
            command=self._on_stop_click,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_refresh = ttk.Button(
            btn_bar,
            text="Làm mới",
            command=self._on_refresh_click,
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_device_count = ttk.Label(btn_bar, text="0 thiết bị")
        self.lbl_device_count.pack(side=tk.RIGHT)

    def _init_settings_frame(self, parent: ttk.Frame) -> None:
        """Khung cấu hình tuỳ chọn scrcpy."""
        frame = ttk.LabelFrame(
            parent,
            text="Tuỳ chọn scrcpy (áp dụng cho lần mở tiếp theo)",
            padding=10,
        )
        frame.pack(fill=tk.X, pady=(0, 5))

        # Dòng 1: Comboboxes
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=(0, 6))

        # Max size
        ttk.Label(row1, text="Độ phân giải tối đa:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_max_size = tk.StringVar(value=self.settings.max_size)
        cb_max_size = ttk.Combobox(
            row1,
            textvariable=self.var_max_size,
            values=MAX_SIZE_OPTIONS,
            state="readonly",
            width=14,
        )
        cb_max_size.pack(side=tk.LEFT, padx=(0, 16))
        cb_max_size.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # Bitrate
        ttk.Label(row1, text="Bitrate:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_bitrate = tk.StringVar(value=self.settings.bitrate)
        cb_bitrate = ttk.Combobox(
            row1,
            textvariable=self.var_bitrate,
            values=BITRATE_OPTIONS,
            state="readonly",
            width=8,
        )
        cb_bitrate.pack(side=tk.LEFT, padx=(0, 16))
        cb_bitrate.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # Max FPS
        ttk.Label(row1, text="FPS tối đa:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_max_fps = tk.StringVar(value=self.settings.max_fps)
        cb_max_fps = ttk.Combobox(
            row1,
            textvariable=self.var_max_fps,
            values=MAX_FPS_OPTIONS,
            state="readonly",
            width=12,
        )
        cb_max_fps.pack(side=tk.LEFT)
        cb_max_fps.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # Dòng 2: Checkboxes
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=(0, 6))

        self.var_no_audio = tk.BooleanVar(value=self.settings.no_audio)
        chk_no_audio = ttk.Checkbutton(
            row2,
            text="Tắt âm thanh",
            variable=self.var_no_audio,
            command=self._save_current_settings,
        )
        chk_no_audio.pack(side=tk.LEFT, padx=(0, 12))

        self.var_turn_screen_off = tk.BooleanVar(value=self.settings.turn_screen_off)
        chk_screen_off = ttk.Checkbutton(
            row2,
            text="Tắt màn hình ĐT",
            variable=self.var_turn_screen_off,
            command=self._save_current_settings,
        )
        chk_screen_off.pack(side=tk.LEFT, padx=(0, 12))

        self.var_stay_awake = tk.BooleanVar(value=self.settings.stay_awake)
        chk_stay_awake = ttk.Checkbutton(
            row2,
            text="Giữ máy thức",
            variable=self.var_stay_awake,
            command=self._save_current_settings,
        )
        chk_stay_awake.pack(side=tk.LEFT, padx=(0, 12))

        self.var_always_on_top = tk.BooleanVar(value=self.settings.always_on_top)
        chk_always_on_top = ttk.Checkbutton(
            row2,
            text="Luôn ở trên",
            variable=self.var_always_on_top,
            command=self._save_current_settings,
        )
        chk_always_on_top.pack(side=tk.LEFT, padx=(0, 12))

        self.var_fullscreen = tk.BooleanVar(value=self.settings.fullscreen)
        chk_fullscreen = ttk.Checkbutton(
            row2,
            text="Toàn màn hình",
            variable=self.var_fullscreen,
            command=self._save_current_settings,
        )
        chk_fullscreen.pack(side=tk.LEFT)

        # Dòng 3: Tham số thêm
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X)

        ttk.Label(row3, text="Tham số thêm:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_extra_args = tk.StringVar(value=self.settings.extra_args)
        entry_extra = ttk.Entry(row3, textvariable=self.var_extra_args)
        entry_extra.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        entry_extra.bind("<FocusOut>", lambda e: self._save_current_settings())

    def _init_status_bar(self) -> None:
        """Khởi tạo thanh trạng thái dưới cùng."""
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(6, 3))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_status = ttk.Label(status_frame, text="Sẵn sàng")
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        info_text = f"adb: {self.adb_bin or 'Không tìm thấy'} | scrcpy: {self.scrcpy_bin or 'Không tìm thấy'}"
        lbl_info = ttk.Label(status_frame, text=info_text, foreground="#666666")
        lbl_info.pack(side=tk.RIGHT)

    def _set_status(self, text: str) -> None:
        """Cập nhật văn bản thanh trạng thái."""
        self.lbl_status.config(text=text)

    def _save_current_settings(self) -> None:
        """Cập nhật đối tượng settings và lưu ra tệp JSON."""
        self.settings.max_size = self.var_max_size.get()
        self.settings.bitrate = self.var_bitrate.get()
        self.settings.max_fps = self.var_max_fps.get()
        self.settings.no_audio = self.var_no_audio.get()
        self.settings.turn_screen_off = self.var_turn_screen_off.get()
        self.settings.stay_awake = self.var_stay_awake.get()
        self.settings.always_on_top = self.var_always_on_top.get()
        self.settings.fullscreen = self.var_fullscreen.get()
        self.settings.extra_args = self.var_extra_args.get()
        save_settings(self.settings)

    def _init_timer(self) -> None:
        """Bắt đầu vòng lặp làm mới định kỳ mỗi 3 giây."""
        self._refresh_device_list_async()
        self.root.after(3000, self._periodic_refresh)

    def _periodic_refresh(self) -> None:
        """Hàm gọi định kỳ kiểm tra tiến trình và quét thiết bị."""
        if self._closing:
            return

        # Kiểm tra các tiến trình vừa thoát
        self._check_exited_sessions()

        # Quét lại thiết bị nền
        self._refresh_device_list_async()

        # Đặt lại lịch 3 giây
        if not self._closing:
            self.root.after(3000, self._periodic_refresh)

    def _check_exited_sessions(self) -> None:
        """Kiểm tra tiến trình scrcpy đã kết thúc và báo lỗi nếu có."""
        exited = self.launcher.check_exited()
        for serial, code, stderr_msg in exited:
            dev = self.devices_by_serial.get(serial)
            name = dev.display_model if dev else serial
            if code != 0:
                err_excerpt = "\n".join(stderr_msg.splitlines()[-6:]) if stderr_msg else "(Không có log stderr)"
                msg = (
                    f"Tiến trình scrcpy cho '{name}' ({serial}) đã kết thúc với mã lỗi {code}.\n\n"
                    f"Chi tiết stderr:\n{err_excerpt}"
                )
                self._set_status(f"Cửa sổ {name} kết thúc với lỗi {code}")
                messagebox.showerror("scrcpy kết thúc với lỗi", msg)
            else:
                self._set_status(f"Cửa sổ scrcpy cho {name} đã đóng")

        if exited:
            self._update_treeview_rows()
            self._update_button_states()

    def _refresh_device_list_async(self) -> None:
        """Lấy danh sách thiết bị trong thread nền."""
        if self._refreshing or self._closing:
            return
        self._refreshing = True

        def worker():
            try:
                devices = adb.list_devices(adb_bin=self.adb_bin, timeout=5.0)
            except Exception:
                devices = []
            if not self._closing:
                self.root.after(0, lambda: self._on_device_list_ready(devices))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_device_list_ready(self, devices: List[adb.DeviceInfo]) -> None:
        """Cập nhật Treeview khi có dữ liệu thiết bị từ thread nền."""
        self._refreshing = False
        if self._closing:
            return

        self.devices_by_serial = {d.serial: d for d in devices}
        self._update_treeview_rows()
        self._update_button_states()
        self.lbl_device_count.config(text=f"{len(devices)} thiết bị")

    def _update_treeview_rows(self) -> None:
        """Vẽ lại hoặc cập nhật các dòng trong Treeview."""
        # Lưu lại serial đang chọn hiện tại
        selected_serial = self._get_selected_serial()

        # Xoá các mục cũ
        existing_items = self.tree.get_children()
        for item in existing_items:
            self.tree.delete(item)

        to_select = None
        for dev in self.devices_by_serial.values():
            if self.launcher.is_running(dev.serial):
                status_text = "Đang hiển thị"
            else:
                status_text = dev.state_display

            item_id = self.tree.insert(
                "",
                tk.END,
                iid=dev.serial,
                values=(
                    dev.display_model,
                    dev.serial,
                    dev.transport_display,
                    status_text,
                ),
            )
            if dev.serial == selected_serial:
                to_select = item_id

        # Phục hồi lựa chọn nếu còn tồn tại
        if to_select and self.tree.exists(to_select):
            self.tree.selection_set(to_select)
            self.tree.focus(to_select)

    def _get_selected_serial(self) -> Optional[str]:
        """Lấy serial của dòng đang được chọn trong Treeview."""
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    def _on_device_selected(self, event=None) -> None:
        """Xử lý khi người dùng chọn một dòng thiết bị."""
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Cập nhật trạng thái enabled/disabled của các nút theo thiết bị chọn."""
        serial = self._get_selected_serial()
        if not serial or serial not in self.devices_by_serial:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_switch_wifi.config(state=tk.DISABLED)
            self.btn_disconnect.config(state=tk.DISABLED)
            return

        dev = self.devices_by_serial[serial]
        is_running = self.launcher.is_running(serial)

        # Nút "Hiển thị": Chỉ bật khi trạng thái là device và chưa chạy
        if dev.state == "device" and not is_running:
            self.btn_start.config(state=tk.NORMAL)
        else:
            self.btn_start.config(state=tk.DISABLED)

        # Nút "Dừng": Bật khi đang chạy
        if is_running:
            self.btn_stop.config(state=tk.NORMAL)
        else:
            self.btn_stop.config(state=tk.DISABLED)

        # Nút "Chuyển sang Wi-Fi": Chỉ bật cho USB ở trạng thái device
        if dev.transport == "usb" and dev.state == "device":
            self.btn_switch_wifi.config(state=tk.NORMAL)
        else:
            self.btn_switch_wifi.config(state=tk.DISABLED)

        # Nút "Ngắt kết nối": Chỉ bật cho thiết bị Wi-Fi
        if dev.transport == "wifi":
            self.btn_disconnect.config(state=tk.NORMAL)
        else:
            self.btn_disconnect.config(state=tk.DISABLED)

    def _on_device_double_click(self, event) -> None:
        """Double-click một dòng = Hiển thị."""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        serial = item
        dev = self.devices_by_serial.get(serial)
        if dev and dev.state == "device" and not self.launcher.is_running(serial):
            self._start_scrcpy_for_device(dev)

    def _on_start_click(self) -> None:
        """Bấm nút Hiển thị."""
        serial = self._get_selected_serial()
        if not serial:
            return
        dev = self.devices_by_serial.get(serial)
        if not dev:
            return

        if dev.state != "device":
            messagebox.showwarning(
                "Không thể mở",
                f"Thiết bị đang ở trạng thái '{dev.state_display}'. Không thể hiển thị màn hình.",
            )
            return

        self._start_scrcpy_for_device(dev)

    def _start_scrcpy_for_device(self, dev: adb.DeviceInfo) -> None:
        """Khởi chạy scrcpy cho thiết bị được chỉ định."""
        if not self.scrcpy_bin:
            messagebox.showerror(
                "Không tìm thấy scrcpy",
                "Không tìm thấy tệp thực thi scrcpy trong hệ thống. Vui lòng cài đặt scrcpy.",
            )
            return

        self._save_current_settings()

        try:
            self.launcher.start(
                serial=dev.serial,
                model=dev.model,
                settings=self.settings,
            )
            self._set_status(f"Đã mở cửa sổ scrcpy: {dev.display_model} ({dev.serial})")
        except Exception as e:
            messagebox.showerror("Lỗi khởi chạy", f"Không thể khởi chạy scrcpy: {e}")
            return

        self._update_treeview_rows()
        self._update_button_states()

    def _on_stop_click(self) -> None:
        """Bấm nút Dừng."""
        serial = self._get_selected_serial()
        if not serial:
            return
        dev = self.devices_by_serial.get(serial)
        name = dev.display_model if dev else serial

        self.launcher.stop(serial)
        self._set_status(f"Đã dừng cửa sổ scrcpy cho {name}")
        self._update_treeview_rows()
        self._update_button_states()

    def _on_refresh_click(self) -> None:
        """Bấm nút Làm mới."""
        self._set_status("Đang quét danh sách thiết bị...")
        self._check_exited_sessions()
        self._refresh_device_list_async()

    def _on_connect_wifi_click(self) -> None:
        """Kết nối thiết bị Wi-Fi từ ô nhập IP:port."""
        target = self.wifi_ip_var.get().strip()
        if not target:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập địa chỉ IP hoặc IP:cổng.")
            return

        self._set_status(f"Đang kết nối tới {target}...")
        self.btn_connect.config(state=tk.DISABLED)

        def worker():
            ok, msg = adb.connect_wifi(target, adb_bin=self.adb_bin, timeout=10.0)

            def finish():
                self.btn_connect.config(state=tk.NORMAL)
                self._set_status(msg)
                if not ok:
                    messagebox.showerror("Lỗi kết nối", msg)
                else:
                    self.wifi_ip_var.set("")
                self._refresh_device_list_async()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_switch_wifi_click(self) -> None:
        """Chuyển thiết bị USB đang chọn sang Wi-Fi."""
        serial = self._get_selected_serial()
        if not serial:
            return
        dev = self.devices_by_serial.get(serial)
        name = dev.display_model if dev else serial

        self._set_status(f"Đang chuyển {name} sang Wi-Fi (lấy IP, bật tcpip 5555)...")
        self.btn_switch_wifi.config(state=tk.DISABLED)

        def worker():
            ok, msg, ip = adb.switch_to_wifi(serial, adb_bin=self.adb_bin, timeout=10.0)

            def finish():
                self.btn_switch_wifi.config(state=tk.NORMAL)
                self._set_status(msg)
                if ok:
                    messagebox.showinfo("Thành công", msg)
                else:
                    messagebox.showerror("Lỗi chuyển sang Wi-Fi", msg)
                self._refresh_device_list_async()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_disconnect_wifi_click(self) -> None:
        """Ngắt kết nối thiết bị Wi-Fi đang chọn."""
        serial = self._get_selected_serial()
        if not serial:
            return

        self._set_status(f"Đang ngắt kết nối {serial}...")
        self.btn_disconnect.config(state=tk.DISABLED)

        def worker():
            ok, msg = adb.disconnect_wifi(serial, adb_bin=self.adb_bin, timeout=10.0)

            def finish():
                self.btn_disconnect.config(state=tk.NORMAL)
                self._set_status(msg)
                if not ok:
                    messagebox.showerror("Lỗi ngắt kết nối", msg)
                self._refresh_device_list_async()

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_closing(self) -> None:
        """Xử lý đóng ứng dụng."""
        if self.launcher.has_active_sessions():
            # Hỏi người dùng có muốn dừng các cửa sổ đang mở không
            ans = messagebox.askyesnocancel(
                "Xác nhận thoát",
                "Có cửa sổ scrcpy đang mở. Bạn có muốn dừng tất cả các cửa sổ trước khi thoát không?\n\n"
                "- Chọn 'Có' (Yes) để dừng tất cả và thoát\n"
                "- Chọn 'Không' (No) để giữ nguyên cửa sổ scrcpy và thoát\n"
                "- Chọn 'Huỷ' (Cancel) để không thoát",
            )
            if ans is None:
                # Huỷ bỏ thoát
                return
            elif ans is True:
                # Dừng tất cả rồi thoát
                self.launcher.stop_all()

        self._closing = True
        self.root.destroy()


def main() -> None:
    """Điểm khởi chạy ứng dụng."""
    root = tk.Tk(className=WM_CLASS_NAME)
    set_window_icon(root)
    app = ScrcpyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
