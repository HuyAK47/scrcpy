"""Giao diện người dùng Tkinter hiện đại cho scrcpy-gui."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import adb
from .binaries import find_adb, find_scrcpy
from .launcher import Launcher
from .preview import (
    PreviewManager,
    build_live_command,
    compute_subsample_factor,
    compute_tile_geometry,
    parse_png_dimensions,
)
from .settings import (
    BITRATE_OPTIONS,
    MAX_FPS_OPTIONS,
    MAX_SIZE_OPTIONS,
    PREVIEW_INTERVAL_OPTIONS,
    Settings,
    load_settings,
    save_settings,
)
from .theme import (
    BANNER_WARN_BG,
    BANNER_WARN_BORDER,
    BANNER_WARN_FG,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    BORDER,
    STATUS_OFFLINE,
    STATUS_ONLINE,
    STATUS_RUNNING,
    STATUS_UNAUTHORIZED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    Card,
    apply_theme,
    get_font,
    get_mono_font,
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


class PreviewCard(Card):
    """Ô hiển thị ảnh thu nhỏ và thông tin cho 1 thiết bị trong tab Xem trước."""

    def __init__(
        self,
        master: tk.Widget,
        dev: adb.DeviceInfo,
        dot_registry: Any,
        on_open: Callable[[adb.DeviceInfo], None],
    ):
        super().__init__(master, padding=(10, 8), width=210)
        self.dev = dev
        self.dot_registry = dot_registry
        self.on_open = on_open
        self.current_photo: Optional[tk.PhotoImage] = None

        self._build_ui()
        self.update_device_info(dev, is_running=False, preview_enabled=False)

    def _build_ui(self) -> None:
        # 1. Hàng tiêu đề: chấm trạng thái + tên máy + badge "Đang mở"
        header = tk.Frame(self, bg=self.bg_color)
        header.pack(fill=tk.X, pady=(0, 2))

        self.lbl_dot = tk.Label(header, bg=self.bg_color)
        self.lbl_dot.pack(side=tk.LEFT, padx=(0, 4))

        self.lbl_model = tk.Label(
            header,
            text=self.dev.display_model,
            bg=self.bg_color,
            fg=TEXT_PRIMARY,
            font=get_font(9, "bold"),
            anchor=tk.W,
        )
        self.lbl_model.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_badge = tk.Label(
            header,
            text="Đang mở",
            bg="#134e4a",
            fg="#2dd4bf",
            font=get_font(8, "bold"),
            padx=4,
            pady=1,
        )

        # 2. Hàng Serial
        self.lbl_serial = tk.Label(
            self,
            text=self.dev.serial,
            bg=self.bg_color,
            fg=TEXT_SECONDARY,
            font=get_mono_font(8),
            anchor=tk.W,
        )
        self.lbl_serial.pack(fill=tk.X, pady=(0, 6))

        # 3. Khung hiển thị ảnh thu nhỏ (kích thước cố định để lưới đồng đều)
        self.img_container = tk.Frame(self, bg=BG_INPUT, width=190, height=220)
        self.img_container.pack_propagate(False)
        self.img_container.pack(fill=tk.X, pady=(0, 4))

        self.lbl_image = tk.Label(
            self.img_container,
            bg=BG_INPUT,
            fg=TEXT_MUTED,
            font=get_font(8),
            justify=tk.CENTER,
            wraplength=170,
        )
        self.lbl_image.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 4. Nhãn hiển thị thông báo lỗi ngắn nếu có
        self.lbl_error = tk.Label(
            self,
            text="",
            bg=self.bg_color,
            fg="#f87171",
            font=get_font(8),
            wraplength=190,
            justify=tk.CENTER,
        )
        self.lbl_error.pack(fill=tk.X, pady=(0, 4))

        # 5. Nút bấm mở scrcpy
        self.btn_open = ttk.Button(
            self,
            text="Mở scrcpy",
            command=self._on_btn_click,
            style="Secondary.TButton",
        )
        self.btn_open.pack(fill=tk.X)

        # Gắn double-click cho các widget trừ nút bấm
        for w in (self, header, self.lbl_dot, self.lbl_model, self.lbl_serial, self.img_container, self.lbl_image, self.lbl_error):
            w.bind("<Double-1>", lambda e: self.on_open(self.dev))

    def _on_btn_click(self) -> None:
        self.on_open(self.dev)

    def update_device_info(
        self,
        dev: adb.DeviceInfo,
        is_running: bool,
        preview_enabled: bool,
    ) -> None:
        self.dev = dev
        self.lbl_model.config(text=dev.display_model)
        self.lbl_serial.config(text=dev.serial)

        # Cập nhật chấm trạng thái
        state_key = "running" if is_running else dev.state
        dot_img = self.dot_registry.get(state_key) if self.dot_registry else None
        if dot_img:
            self.lbl_dot.config(image=dot_img)

        # Cập nhật badge đang mở
        if is_running:
            self.lbl_badge.pack(side=tk.RIGHT)
        else:
            self.lbl_badge.pack_forget()

        # Cập nhật nút điều khiển
        if is_running:
            self.btn_open.config(text="Đang hiển thị", state=tk.DISABLED)
        elif dev.state == "device":
            self.btn_open.config(text="Mở scrcpy", state=tk.NORMAL)
        else:
            self.btn_open.config(text=dev.state_display, state=tk.DISABLED)

        # Cập nhật khung hình ảnh preview
        if dev.state != "device":
            self.current_photo = None
            self.img_container.config(bg="#1a202c")
            self.lbl_image.config(
                image="",
                text=f"⚠️ {dev.state_display}\n(Không có xem trước)",
                bg="#1a202c",
                fg=TEXT_MUTED,
            )
            self.lbl_error.config(text="")
        elif not preview_enabled:
            self.current_photo = None
            self.img_container.config(bg=BG_INPUT)
            self.lbl_image.config(
                image="",
                text="Xem trước đang tắt\nNhấp đúp hoặc bấm Mở",
                bg=BG_INPUT,
                fg=TEXT_MUTED,
            )
            self.lbl_error.config(text="")
        else:
            self.img_container.config(bg=BG_INPUT)
            self.lbl_image.config(bg=BG_INPUT)
            if self.current_photo:
                self.lbl_image.config(image=self.current_photo, text="")
            else:
                self.lbl_image.config(image="", text="Đang chụp...", fg=TEXT_MUTED)

    def set_image(self, photo: tk.PhotoImage) -> None:
        """Cập nhật ảnh chụp màn hình thu nhỏ mới."""
        self.current_photo = photo
        self.lbl_image.config(image=self.current_photo, text="")
        self.lbl_error.config(text="")

    def set_error(self, err_msg: str) -> None:
        """Cập nhật lỗi chụp: hiển thị thông báo ngắn và giữ ảnh cũ nếu có."""
        short_err = err_msg.splitlines()[0] if err_msg else "Lỗi chụp"
        if len(short_err) > 38:
            short_err = short_err[:35] + "..."
        self.lbl_error.config(text=f"⚠️ {short_err}")
        if self.current_photo is None:
            self.lbl_image.config(image="", text=f"⚠️ {short_err}", fg="#f87171")


class ScrcpyApp:
    """Ứng dụng giao diện chính."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("scrcpy GUI - Điều khiển thiết bị Android")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)

        # Áp dụng chủ đề tối công nghệ và quản lý chấm trạng thái
        self.dot_registry = apply_theme(self.root)

        # Trạng thái binary
        self.adb_bin = find_adb()
        self.scrcpy_bin = find_scrcpy()

        # Quản lý tiến trình & cài đặt
        self.launcher = Launcher(scrcpy_bin=self.scrcpy_bin)
        self.live_launcher = Launcher(scrcpy_bin=self.scrcpy_bin)
        self.settings: Settings = load_settings()

        # Quản lý xem trước preview
        self.preview_manager = PreviewManager(adb_bin=self.adb_bin, max_workers=4, timeout=8.0)
        self._preview_timer_id: Optional[str] = None
        self._preview_cards: Dict[str, PreviewCard] = {}
        self._last_canvas_width: Optional[int] = None

        # Bộ nhớ thiết bị hiện tại {serial: DeviceInfo}
        self.devices_by_serial: Dict[str, adb.DeviceInfo] = {}
        self._refreshing = False
        self._closing = False

        self._init_ui()
        self._init_timer()

        # Xử lý sự kiện đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _init_ui(self) -> None:
        """Khởi tạo bố cục giao diện dạng thẻ với Notebook."""
        main_container = tk.Frame(self.root, bg=BG_DARK, padx=16, pady=12)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 1. Cảnh báo nếu thiếu binary
        self._init_banner(main_container)

        # 2. Bảng phân tab Notebook: "Thiết bị" và "Xem trước"
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_devices = tk.Frame(self.notebook, bg=BG_DARK)
        self.tab_preview = tk.Frame(self.notebook, bg=BG_DARK)

        self.notebook.add(self.tab_devices, text="Thiết bị")
        self.notebook.add(self.tab_preview, text="Xem trước")

        # Nội dung tab "Thiết bị" (giữ nguyên toàn bộ hành vi)
        self._init_wifi_frame(self.tab_devices)
        self._init_device_list_frame(self.tab_devices)
        self._init_settings_frame(self.tab_devices)

        # Nội dung tab "Xem trước"
        self._init_preview_tab(self.tab_preview)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # 3. Thanh trạng thái dưới đáy
        self._init_status_bar()

    def _init_banner(self, parent: tk.Widget) -> None:
        """Hiển thị cảnh báo nếu không tìm thấy adb hoặc scrcpy."""
        missing = []
        if not self.adb_bin:
            missing.append("adb")
        if not self.scrcpy_bin:
            missing.append("scrcpy")

        if missing:
            msg = (
                f"⚠️  Cảnh báo: Không tìm thấy lệnh thực thi '{', '.join(missing)}'.\n"
                "Vui lòng đảm bảo các công cụ đã được cài đặt trong PATH hoặc qua biến môi trường ADB / SCRCPY_BIN."
            )
            banner = tk.Label(
                parent,
                text=msg,
                bg=BANNER_WARN_BG,
                fg=BANNER_WARN_FG,
                padx=14,
                pady=8,
                justify=tk.LEFT,
                font=get_font(9),
                highlightbackground=BANNER_WARN_BORDER,
                highlightcolor=BANNER_WARN_BORDER,
                highlightthickness=1,
            )
            banner.pack(fill=tk.X, pady=(0, 10))

    def _init_wifi_frame(self, parent: tk.Widget) -> None:
        """Khu vực kết nối mạng Wi-Fi dạng thẻ."""
        card = Card(parent, padding=(14, 10))
        card.pack(fill=tk.X, pady=(0, 10))

        card.add_header(
            title="📶  Kết nối Wi-Fi",
            subtitle="kết nối thiết bị qua mạng nội bộ (mặc định cổng 5555)",
        )

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill=tk.X)

        tk.Label(
            row,
            text="Địa chỉ IP[:cổng]:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.wifi_ip_var = tk.StringVar(value="")
        self.wifi_entry = ttk.Entry(
            row,
            textvariable=self.wifi_ip_var,
            width=24,
            font=get_mono_font(9),
        )
        self.wifi_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.wifi_entry.bind("<Return>", lambda e: self._on_connect_wifi_click())

        self.btn_connect = ttk.Button(
            row,
            text="Kết nối",
            command=self._on_connect_wifi_click,
            style="Secondary.TButton",
        )
        self.btn_connect.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_switch_wifi = ttk.Button(
            row,
            text="Chuyển sang Wi-Fi",
            command=self._on_switch_wifi_click,
            style="Secondary.TButton",
            state=tk.DISABLED,
        )
        self.btn_switch_wifi.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_disconnect = ttk.Button(
            row,
            text="Ngắt kết nối",
            command=self._on_disconnect_wifi_click,
            style="Secondary.TButton",
            state=tk.DISABLED,
        )
        self.btn_disconnect.pack(side=tk.LEFT, padx=(0, 6))

    def _init_device_list_frame(self, parent: tk.Widget) -> None:
        """Danh sách thiết bị kết nối dạng thẻ."""
        card = Card(parent, padding=(14, 12))
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        _, _, self.lbl_device_count = card.add_header(
            title="📱  Danh sách thiết bị",
            subtitle="chọn thiết bị để điều khiển hoặc nhấp đúp để mở màn hình",
            badge_text="0 thiết bị",
        )

        # Treeview + Scrollbar
        tree_container = tk.Frame(card, bg=BG_CARD)
        tree_container.pack(fill=tk.BOTH, expand=True)

        columns = ("model", "serial", "transport", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            height=6,
        )

        # Cột #0 dành cho chấm trạng thái màu
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=36, minwidth=36, stretch=False, anchor=tk.CENTER)

        self.tree.heading("model", text="Tên máy")
        self.tree.heading("serial", text="Serial")
        self.tree.heading("transport", text="Kết nối")
        self.tree.heading("status", text="Trạng thái")

        self.tree.column("model", width=220, minwidth=140, stretch=True)
        self.tree.column("serial", width=190, minwidth=140, stretch=False)
        self.tree.column("transport", width=90, minwidth=80, stretch=False, anchor=tk.CENTER)
        self.tree.column("status", width=200, minwidth=160, stretch=False)

        # Cấu hình màu chữ theo tag trạng thái
        self.tree.tag_configure("device", foreground=TEXT_PRIMARY)
        self.tree.tag_configure("running", foreground=STATUS_RUNNING)
        self.tree.tag_configure("unauthorized", foreground=STATUS_UNAUTHORIZED)
        self.tree.tag_configure("offline", foreground=STATUS_OFFLINE)
        self.tree.tag_configure("unknown", foreground=TEXT_MUTED)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_device_selected)
        self.tree.bind("<Double-1>", self._on_device_double_click)

        # Dòng nhắc khi chưa có thiết bị nào
        self.lbl_empty_hint = tk.Label(
            card,
            text="Chưa kết nối thiết bị nào. Cắm cáp USB (đã bật Gỡ lỗi USB) hoặc nhập IP để kết nối Wi-Fi.",
            bg=BG_CARD,
            fg=TEXT_MUTED,
            font=get_font(9),
        )
        self.lbl_empty_hint.pack(fill=tk.X, pady=(6, 0))

        # Thanh nút điều khiển
        btn_bar = tk.Frame(card, bg=BG_CARD)
        btn_bar.pack(fill=tk.X, pady=(10, 0))

        self.btn_start = ttk.Button(
            btn_bar,
            text="▶  Hiển thị",
            command=self._on_start_click,
            style="Accent.TButton",
            state=tk.DISABLED,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(
            btn_bar,
            text="■  Dừng",
            command=self._on_stop_click,
            style="Danger.TButton",
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_refresh = ttk.Button(
            btn_bar,
            text="⟳  Làm mới",
            command=self._on_refresh_click,
            style="Secondary.TButton",
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=(0, 8))

    def _init_settings_frame(self, parent: tk.Widget) -> None:
        """Khung cấu hình tuỳ chọn scrcpy dạng thẻ."""
        card = Card(parent, padding=(14, 10))
        card.pack(fill=tk.X, pady=(0, 4))

        card.add_header(
            title="⚙️  Tuỳ chọn scrcpy",
            subtitle="áp dụng cho lần mở tiếp theo",
        )

        # Dòng 1: Comboboxes
        row1 = tk.Frame(card, bg=BG_CARD)
        row1.pack(fill=tk.X, pady=(0, 8))

        # Max size
        tk.Label(
            row1,
            text="Độ phân giải tối đa:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.var_max_size = tk.StringVar(value=self.settings.max_size)
        cb_max_size = ttk.Combobox(
            row1,
            textvariable=self.var_max_size,
            values=MAX_SIZE_OPTIONS,
            state="readonly",
            width=15,
        )
        cb_max_size.pack(side=tk.LEFT, padx=(0, 16))
        cb_max_size.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # Bitrate
        tk.Label(
            row1,
            text="Bitrate:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.var_bitrate = tk.StringVar(value=self.settings.bitrate)
        cb_bitrate = ttk.Combobox(
            row1,
            textvariable=self.var_bitrate,
            values=BITRATE_OPTIONS,
            state="readonly",
            width=12,
        )
        cb_bitrate.pack(side=tk.LEFT, padx=(0, 16))
        cb_bitrate.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # FPS tối đa
        tk.Label(
            row1,
            text="FPS tối đa:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.var_max_fps = tk.StringVar(value=self.settings.max_fps)
        cb_max_fps = ttk.Combobox(
            row1,
            textvariable=self.var_max_fps,
            values=MAX_FPS_OPTIONS,
            state="readonly",
            width=14,
        )
        cb_max_fps.pack(side=tk.LEFT)
        cb_max_fps.bind("<<ComboboxSelected>>", lambda e: self._save_current_settings())

        # Dòng 2: Checkboxes
        row2 = tk.Frame(card, bg=BG_CARD)
        row2.pack(fill=tk.X, pady=(0, 8))

        self.var_no_audio = tk.BooleanVar(value=self.settings.no_audio)
        chk_no_audio = ttk.Checkbutton(
            row2,
            text="Tắt âm thanh",
            variable=self.var_no_audio,
            command=self._save_current_settings,
        )
        chk_no_audio.pack(side=tk.LEFT, padx=(0, 14))

        self.var_turn_screen_off = tk.BooleanVar(value=self.settings.turn_screen_off)
        chk_screen_off = ttk.Checkbutton(
            row2,
            text="Tắt màn hình ĐT",
            variable=self.var_turn_screen_off,
            command=self._save_current_settings,
        )
        chk_screen_off.pack(side=tk.LEFT, padx=(0, 14))

        self.var_stay_awake = tk.BooleanVar(value=self.settings.stay_awake)
        chk_stay_awake = ttk.Checkbutton(
            row2,
            text="Giữ máy thức",
            variable=self.var_stay_awake,
            command=self._save_current_settings,
        )
        chk_stay_awake.pack(side=tk.LEFT, padx=(0, 14))

        self.var_always_on_top = tk.BooleanVar(value=self.settings.always_on_top)
        chk_always_on_top = ttk.Checkbutton(
            row2,
            text="Luôn ở trên",
            variable=self.var_always_on_top,
            command=self._save_current_settings,
        )
        chk_always_on_top.pack(side=tk.LEFT, padx=(0, 14))

        self.var_fullscreen = tk.BooleanVar(value=self.settings.fullscreen)
        chk_fullscreen = ttk.Checkbutton(
            row2,
            text="Toàn màn hình",
            variable=self.var_fullscreen,
            command=self._save_current_settings,
        )
        chk_fullscreen.pack(side=tk.LEFT)

        # Dòng 3: Tham số thêm
        row3 = tk.Frame(card, bg=BG_CARD)
        row3.pack(fill=tk.X)

        tk.Label(
            row3,
            text="Tham số thêm:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.var_extra_args = tk.StringVar(value=self.settings.extra_args)
        entry_extra = ttk.Entry(row3, textvariable=self.var_extra_args)
        entry_extra.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry_extra.bind("<FocusOut>", lambda e: self._save_current_settings())

    def _init_preview_tab(self, parent: tk.Widget) -> None:
        """Khởi tạo giao diện lưới xem trước màn hình trong tab 'Xem trước'."""
        # 1. Thanh điều khiển trên đỉnh tab Xem trước
        ctrl_card = Card(parent, padding=(14, 10))
        ctrl_card.pack(fill=tk.X, pady=(0, 10))

        ctrl_inner = tk.Frame(ctrl_card, bg=BG_CARD)
        ctrl_inner.pack(fill=tk.X)

        # Công tắc Bật xem trước
        self.var_preview_enabled = tk.BooleanVar(value=self.settings.preview_enabled)
        self.chk_preview_enabled = ttk.Checkbutton(
            ctrl_inner,
            text="Bật xem trước",
            variable=self.var_preview_enabled,
            command=self._on_preview_toggle,
        )
        self.chk_preview_enabled.pack(side=tk.LEFT, padx=(0, 16))

        # Chu kỳ làm mới
        tk.Label(
            ctrl_inner,
            text="Chu kỳ làm mới:",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.var_preview_interval = tk.StringVar(value=f"{self.settings.preview_interval}s")
        self.cb_preview_interval = ttk.Combobox(
            ctrl_inner,
            textvariable=self.var_preview_interval,
            values=PREVIEW_INTERVAL_OPTIONS,
            state="readonly",
            width=6,
        )
        self.cb_preview_interval.pack(side=tk.LEFT, padx=(0, 16))
        self.cb_preview_interval.bind("<<ComboboxSelected>>", self._on_preview_interval_changed)

        # Nút Xếp lưới live
        self.btn_live_tiling = ttk.Button(
            ctrl_inner,
            text="⊞  Xếp lưới live",
            command=self._on_toggle_live_tiling,
            style="Secondary.TButton",
        )
        self.btn_live_tiling.pack(side=tk.RIGHT)

        # 2. Vùng lưới cuộn được chứa các ô thiết bị
        grid_container = tk.Frame(parent, bg=BG_DARK)
        grid_container.pack(fill=tk.BOTH, expand=True)

        self.preview_canvas = tk.Canvas(grid_container, bg=BG_DARK, highlightthickness=0)
        preview_scrollbar = ttk.Scrollbar(
            grid_container,
            orient=tk.VERTICAL,
            command=self.preview_canvas.yview,
        )
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_grid_frame = tk.Frame(self.preview_canvas, bg=BG_DARK)
        self._canvas_window_id = self.preview_canvas.create_window(
            (0, 0),
            window=self.preview_grid_frame,
            anchor="nw",
        )

        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Dòng nhắc khi chưa có thiết bị nào
        self.lbl_preview_empty = tk.Label(
            self.preview_grid_frame,
            text="Chưa kết nối thiết bị nào. Cắm cáp USB (đã bật Gỡ lỗi USB) hoặc nhập IP ở tab Thiết bị để kết nối Wi-Fi.",
            bg=BG_DARK,
            fg=TEXT_MUTED,
            font=get_font(9),
        )
        self.lbl_preview_empty.pack(fill=tk.X, pady=(20, 0))

        # Ràng buộc cấu hình thay đổi kích thước và cuộn
        self.preview_canvas.bind("<Configure>", self._on_canvas_configure)
        self.preview_grid_frame.bind(
            "<Configure>",
            lambda e: self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all")),
        )
        self._bind_mousewheel(self.preview_canvas)
        self._bind_mousewheel(self.preview_grid_frame)

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        """Gắn sự kiện cuộn chuột linh hoạt trên nhiều nền tảng."""
        def on_mousewheel(event):
            if event.num == 4:
                self.preview_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.preview_canvas.yview_scroll(1, "units")
            elif event.delta:
                self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind("<Button-4>", on_mousewheel)
        widget.bind("<Button-5>", on_mousewheel)
        widget.bind("<MouseWheel>", on_mousewheel)

    def _on_canvas_configure(self, event) -> None:
        """Tự động co giãn bề ngang frame con theo canvas và sắp lại cột."""
        if getattr(self, "_last_canvas_width", None) != event.width:
            self._last_canvas_width = event.width
            self.preview_canvas.itemconfig(self._canvas_window_id, width=event.width)
            self._relayout_preview_grid()

    def _relayout_preview_grid(self) -> None:
        """Sắp xếp lại các thẻ thiết bị theo số cột vừa vặn với chiều ngang canvas."""
        if not self._preview_cards:
            return

        width = self.preview_canvas.winfo_width()
        if width <= 1:
            width = 900

        card_width = 210
        gap = 14
        cols = max(1, (width - 16) // (card_width + gap))

        for idx, card in enumerate(self._preview_cards.values()):
            row = idx // cols
            col = idx % cols
            card.grid(row=row, column=col, padx=gap // 2, pady=gap // 2, sticky="n")

        self.preview_grid_frame.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _init_status_bar(self) -> None:
        """Khởi tạo thanh trạng thái dưới cùng."""
        status_frame = tk.Frame(
            self.root,
            bg=BG_DARK,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=6,
        )
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_status = tk.Label(
            status_frame,
            text="●  Sẵn sàng",
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            font=get_font(9),
        )
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)

        info_text = f"adb: {self.adb_bin or 'Không tìm thấy'} | scrcpy: {self.scrcpy_bin or 'Không tìm thấy'}"
        lbl_info = tk.Label(
            status_frame,
            text=info_text,
            bg=BG_DARK,
            fg=TEXT_SECONDARY,
            font=get_mono_font(8),
        )
        lbl_info.pack(side=tk.RIGHT)

    def _set_status(self, text: str) -> None:
        """Cập nhật văn bản thanh trạng thái."""
        self.lbl_status.config(text=f"●  {text}")

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
        if hasattr(self, "var_preview_enabled"):
            self.settings.preview_enabled = self.var_preview_enabled.get()
        if hasattr(self, "var_preview_interval"):
            val_str = self.var_preview_interval.get().rstrip("sS ").strip()
            try:
                self.settings.preview_interval = int(val_str)
            except ValueError:
                self.settings.preview_interval = 2
        save_settings(self.settings)

    def _on_tab_changed(self, event=None) -> None:
        """Xử lý khi người dùng chuyển đổi tab."""
        if self._closing:
            return

        if self._is_preview_active():
            # Chuyển sang tab Xem trước: kích hoạt preview nếu công tắc đang bật
            self.preview_manager.set_enabled(True)
            self._start_preview_loop()
        else:
            # Rời khỏi tab Xem trước: tạm dừng chụp để tiết kiệm pin/CPU
            if self._preview_timer_id is not None:
                try:
                    self.root.after_cancel(self._preview_timer_id)
                except Exception:
                    pass
                self._preview_timer_id = None
            self.preview_manager.set_enabled(False)

    def _is_preview_active(self) -> bool:
        """Kiểm tra tab Xem trước có đang mở VÀ công tắc xem trước đang bật không."""
        if self._closing:
            return False
        if not getattr(self, "var_preview_enabled", None) or not self.var_preview_enabled.get():
            return False
        try:
            current = self.notebook.select()
            return current == str(self.tab_preview) or self.notebook.tab(current, "text") == "Xem trước"
        except Exception:
            return False

    def _on_preview_toggle(self) -> None:
        """Bật hoặc tắt công tắc xem trước."""
        enabled = self.var_preview_enabled.get()
        self.settings.preview_enabled = enabled
        self._save_current_settings()

        if not enabled:
            if self._preview_timer_id is not None:
                try:
                    self.root.after_cancel(self._preview_timer_id)
                except Exception:
                    pass
                self._preview_timer_id = None
            self.preview_manager.set_enabled(False)

            # Đưa các thẻ về trạng thái placeholder
            for card in self._preview_cards.values():
                card.update_device_info(
                    dev=card.dev,
                    is_running=self.launcher.is_running(card.dev.serial),
                    preview_enabled=False,
                )
            self._set_status("Đã tắt xem trước ảnh màn hình")
        else:
            self._set_status("Đã bật xem trước ảnh màn hình")
            for card in self._preview_cards.values():
                card.update_device_info(
                    dev=card.dev,
                    is_running=self.launcher.is_running(card.dev.serial),
                    preview_enabled=True,
                )
            if self._is_preview_active():
                self.preview_manager.set_enabled(True)
                self._start_preview_loop()

    def _on_preview_interval_changed(self, event=None) -> None:
        """Thay đổi chu kỳ làm mới preview."""
        val_str = self.var_preview_interval.get().rstrip("sS ").strip()
        try:
            val = int(val_str)
        except ValueError:
            val = 2
        self.settings.preview_interval = val
        self._save_current_settings()
        self._set_status(f"Đã đặt chu kỳ làm mới xem trước: {val}s")
        if self._is_preview_active():
            self._start_preview_loop()

    def _start_preview_loop(self) -> None:
        """Khởi động vòng lặp chụp preview định kỳ."""
        if not self._is_preview_active():
            return

        if self._preview_timer_id is not None:
            try:
                self.root.after_cancel(self._preview_timer_id)
            except Exception:
                pass
            self._preview_timer_id = None

        self._preview_tick()

    def _preview_tick(self) -> None:
        """Thực hiện một lượt chụp màn hình cho tất cả thiết bị device."""
        if not self._is_preview_active():
            return

        for dev in self.devices_by_serial.values():
            if dev.state == "device":
                self.preview_manager.start_capture(
                    serial=dev.serial,
                    on_success=self._on_preview_capture_success,
                    on_error=self._on_preview_capture_error,
                )

        interval_ms = max(1, self.settings.preview_interval) * 1000
        self._preview_timer_id = self.root.after(interval_ms, self._preview_tick)

    def _on_preview_capture_success(self, serial: str, data: bytes) -> None:
        """Nhận kết quả chụp thành công từ worker thread."""
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._apply_preview_image(serial, data))
        except Exception:
            pass

    def _on_preview_capture_error(self, serial: str, error_msg: str) -> None:
        """Nhận lỗi chụp từ worker thread."""
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self._apply_preview_error(serial, error_msg))
        except Exception:
            pass

    def _apply_preview_image(self, serial: str, data: bytes) -> None:
        """Hiển thị ảnh chụp lên thẻ trên main thread."""
        if self._closing or not self._is_preview_active():
            return
        card = self._preview_cards.get(serial)
        if not card:
            return
        try:
            orig_w, orig_h = parse_png_dimensions(data)
            factor = compute_subsample_factor(orig_w, orig_h, target_w=190, target_h=220)
            raw_photo = tk.PhotoImage(data=data)
            photo = raw_photo.subsample(factor, factor) if factor > 1 else raw_photo
            card.set_image(photo)
        except Exception as e:
            card.set_error(str(e))

    def _apply_preview_error(self, serial: str, error_msg: str) -> None:
        """Hiển thị lỗi lên thẻ trên main thread và giữ ảnh cũ."""
        if self._closing:
            return
        card = self._preview_cards.get(serial)
        if card:
            card.set_error(error_msg)

    def _on_preview_card_double_click(self, dev: adb.DeviceInfo) -> None:
        """Mở scrcpy cho thiết bị khi double-click hoặc bấm nút Mở trên ô preview."""
        if dev.state != "device":
            self._set_status(f"Thiết bị '{dev.display_model}' chưa sẵn sàng ({dev.state_display})")
            return
        if self.launcher.is_running(dev.serial):
            self._set_status(f"Cửa sổ scrcpy cho '{dev.display_model}' ({dev.serial}) đã đang mở")
            return
        self._start_scrcpy_for_device(dev)

    def _update_preview_grid(self) -> None:
        """Đồng bộ lưới xem trước với danh sách thiết bị hiện có."""
        current_serials = set(self.devices_by_serial.keys())
        existing_serials = set(self._preview_cards.keys())

        # Gỡ bỏ các thẻ thiết bị đã rút
        for s in existing_serials - current_serials:
            card = self._preview_cards.pop(s)
            card.destroy()

        # Thêm mới hoặc cập nhật các thẻ
        for serial, dev in self.devices_by_serial.items():
            is_running = self.launcher.is_running(serial)
            if serial not in self._preview_cards:
                card = PreviewCard(
                    master=self.preview_grid_frame,
                    dev=dev,
                    dot_registry=self.dot_registry,
                    on_open=self._on_preview_card_double_click,
                )
                self._preview_cards[serial] = card
            else:
                card = self._preview_cards[serial]

            card.update_device_info(
                dev=dev,
                is_running=is_running,
                preview_enabled=self.settings.preview_enabled,
            )

        # Cập nhật hiển thị dòng nhắc trống
        if not self.devices_by_serial:
            self.lbl_preview_empty.pack(fill=tk.X, pady=(20, 0))
        else:
            self.lbl_preview_empty.pack_forget()

        self._relayout_preview_grid()

        # Nếu đang ở tab xem trước và có thiết bị mới chưa có ảnh, kích hoạt chụp
        if self._is_preview_active():
            for serial, dev in self.devices_by_serial.items():
                if dev.state == "device" and self._preview_cards[serial].current_photo is None:
                    self.preview_manager.start_capture(
                        serial=serial,
                        on_success=self._on_preview_capture_success,
                        on_error=self._on_preview_capture_error,
                    )

    def _update_preview_cards_running(self) -> None:
        """Cập nhật trạng thái 'Đang hiển thị' trên các thẻ preview."""
        for serial, card in self._preview_cards.items():
            dev = self.devices_by_serial.get(serial)
            if dev:
                card.update_device_info(
                    dev=dev,
                    is_running=self.launcher.is_running(serial),
                    preview_enabled=self.settings.preview_enabled,
                )

    def _on_toggle_live_tiling(self) -> None:
        """Bật hoặc tắt chế độ xếp lưới xem trực tiếp (Live Tiling)."""
        if self.live_launcher.has_active_sessions():
            self.live_launcher.stop_all()
            self.btn_live_tiling.config(text="⊞  Xếp lưới live", style="Secondary.TButton")
            self._set_status("Đã đóng tất cả cửa sổ lưới live")
            return

        live_devs = [d for d in self.devices_by_serial.values() if d.state == "device"]
        if not live_devs:
            messagebox.showinfo(
                "Không có thiết bị",
                "Không có thiết bị nào đang ở trạng thái sẵn sàng để xếp lưới trực tiếp.",
            )
            return

        total = len(live_devs)
        screen_w = max(640, self.root.winfo_screenwidth())
        screen_h = max(480, self.root.winfo_screenheight())

        started = 0
        for idx, dev in enumerate(live_devs):
            geom = compute_tile_geometry(idx, total, screen_w, screen_h)
            cmd = build_live_command(
                serial=dev.serial,
                model=dev.model,
                geometry=geom,
                scrcpy_bin=self.scrcpy_bin,
            )
            try:
                self.live_launcher.start(serial=dev.serial, custom_cmd=cmd)
                started += 1
            except Exception as e:
                self._set_status(f"Lỗi mở live cho {dev.display_model}: {e}")

        if started > 0:
            self.btn_live_tiling.config(text="✕  Đóng lưới live", style="Danger.TButton")
            self._set_status(f"Đã mở lưới live cho {started}/{total} thiết bị")

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
            self._update_preview_cards_running()

        if hasattr(self, "live_launcher"):
            self.live_launcher.check_exited()
            if hasattr(self, "btn_live_tiling") and not self.live_launcher.has_active_sessions():
                self.btn_live_tiling.config(text="⊞  Xếp lưới live", style="Secondary.TButton")

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
                try:
                    self.root.after(0, lambda: self._on_device_list_ready(devices))
                except Exception:
                    pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_device_list_ready(self, devices: List[adb.DeviceInfo]) -> None:
        """Cập nhật Treeview và lưới xem trước khi có dữ liệu thiết bị từ thread nền."""
        self._refreshing = False
        if self._closing:
            return

        self.devices_by_serial = {d.serial: d for d in devices}
        self._update_treeview_rows()
        self._update_button_states()
        self._update_preview_grid()
        if self.lbl_device_count:
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
                state_key = "running"
            else:
                status_text = dev.state_display
                state_key = dev.state

            dot_img = self.dot_registry.get(state_key)

            item_id = self.tree.insert(
                "",
                tk.END,
                iid=dev.serial,
                image=dot_img if dot_img else "",
                values=(
                    dev.display_model,
                    dev.serial,
                    dev.transport_display,
                    status_text,
                ),
                tags=(state_key,),
            )
            if dev.serial == selected_serial:
                to_select = item_id

        # Phục hồi lựa chọn nếu còn tồn tại
        if to_select and self.tree.exists(to_select):
            self.tree.selection_set(to_select)
            self.tree.focus(to_select)

        # Cập nhật hiển thị dòng nhắc khi không có thiết bị
        if not self.devices_by_serial:
            self.lbl_empty_hint.pack(fill=tk.X, pady=(6, 0))
        else:
            self.lbl_empty_hint.pack_forget()

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
        self._update_preview_cards_running()

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
        self._update_preview_cards_running()

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

            if not self._closing:
                try:
                    self.root.after(0, finish)
                except Exception:
                    pass

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

            if not self._closing:
                try:
                    self.root.after(0, finish)
                except Exception:
                    pass

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

            if not self._closing:
                try:
                    self.root.after(0, finish)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_closing(self) -> None:
        """Xử lý đóng ứng dụng."""
        # Dừng các tiến trình và tác vụ xem trước
        if hasattr(self, "preview_manager"):
            self.preview_manager.cancel_all()
        if hasattr(self, "live_launcher"):
            self.live_launcher.stop_all()
        if getattr(self, "_preview_timer_id", None) is not None:
            try:
                self.root.after_cancel(self._preview_timer_id)
            except Exception:
                pass
            self._preview_timer_id = None

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
