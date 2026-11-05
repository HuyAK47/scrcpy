"""Hệ thống chủ đề (theme) tối hiện đại cho scrcpy-gui.

Dựa trên công cụ 'clam' của ttk, cung cấp bảng màu phong cách công nghệ
lấy cảm hứng từ sắc thái xanh lam và vàng kim của biểu tượng Gothic,
bố cục dạng thẻ (card), phân cấp chữ rõ ràng và chấm trạng thái màu.
"""

from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Dict, Optional, Tuple

# Thư mục tài nguyên ảnh
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# ============================================================================
# Bảng màu chủ đề tối (Dark Tech Palette)
# ============================================================================
BG_DARK = "#0f141c"          # Nền cửa sổ chính (xám đen / midnight navy)
BG_CARD = "#161d27"          # Nền thẻ nổi (card)
BG_CARD_HEADER = "#1a2332"   # Nền tiêu đề thẻ / phân đoạn
BG_INPUT = "#0d121a"         # Nền ô nhập liệu, danh sách
BORDER = "#273244"           # Viền thẻ và ô nhập
BORDER_FOCUS = "#388bfd"     # Viền khi focus ô nhập

TEXT_PRIMARY = "#f8fafc"     # Văn bản chính (trắng ngà sắc nét)
TEXT_SECONDARY = "#94a3b8"   # Văn bản phụ / nhãn (slate sáng)
TEXT_MUTED = "#64748b"       # Ghi chú nhỏ / placeholder

# Nút hành động chính (Accent / Hiển thị) - Xanh lam rực rỡ
ACCENT_BG = "#1f6feb"
ACCENT_HOVER = "#388bfd"
ACCENT_PRESSED = "#1158c7"
ACCENT_FG = "#ffffff"

# Nút dừng (Danger / Dừng) - Đỏ thẫm
DANGER_BG = "#dc2626"
DANGER_HOVER = "#ef4444"
DANGER_PRESSED = "#b91c1c"
DANGER_FG = "#ffffff"

# Nút phụ (Secondary / Làm mới, Wi-Fi)
BTN_SEC_BG = "#222b3a"
BTN_SEC_HOVER = "#2d3748"
BTN_SEC_PRESSED = "#1a202c"
BTN_SEC_BORDER = "#334155"
BTN_SEC_FG = "#e2e8f0"

# Trạng thái vô hiệu hoá của nút
BTN_DISABLED_BG = "#161d27"
BTN_DISABLED_FG = "#475569"
BTN_DISABLED_BORDER = "#21262d"

# Màu chấm trạng thái thiết bị
STATUS_ONLINE = "#10b981"       # Xanh lá ngọc (device / online)
STATUS_RUNNING = "#38bdf8"      # Xanh da trời (đang hiển thị màn hình)
STATUS_UNAUTHORIZED = "#f59e0b" # Vàng kim / amber (cần cấp quyền)
STATUS_OFFLINE = "#ef4444"      # Đỏ san hô (offline / lỗi)

# Hộp cảnh báo khi thiếu binary
BANNER_WARN_BG = "#2b1e09"
BANNER_WARN_BORDER = "#d97706"
BANNER_WARN_FG = "#fef08a"

# Huy hiệu (Badge số lượng thiết bị)
BADGE_BG = "#1e293b"
BADGE_FG = "#93c5fd"


# ============================================================================
# Quản lý Phông chữ Hệ thống
# ============================================================================
FONT_FAMILY_FALLBACKS = (
    "Inter",
    "Ubuntu",
    "DejaVu Sans",
    "Liberation Sans",
    "Segoe UI",
    "sans-serif",
)

MONO_FAMILY_FALLBACKS = (
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Ubuntu Mono",
    "monospace",
)

_CACHED_SANS_FAMILY: Optional[str] = None
_CACHED_MONO_FAMILY: Optional[str] = None


def resolve_sans_family() -> str:
    """Tìm phông chữ sans-serif tốt nhất đang có trên hệ thống."""
    global _CACHED_SANS_FAMILY
    if _CACHED_SANS_FAMILY:
        return _CACHED_SANS_FAMILY

    try:
        available = set(tkfont.families())
        for fam in FONT_FAMILY_FALLBACKS:
            if fam in available:
                _CACHED_SANS_FAMILY = fam
                return fam
    except Exception:
        pass
    _CACHED_SANS_FAMILY = "DejaVu Sans"
    return _CACHED_SANS_FAMILY


def resolve_mono_family() -> str:
    """Tìm phông chữ monospace tốt nhất đang có trên hệ thống."""
    global _CACHED_MONO_FAMILY
    if _CACHED_MONO_FAMILY:
        return _CACHED_MONO_FAMILY

    try:
        available = set(tkfont.families())
        for fam in MONO_FAMILY_FALLBACKS:
            if fam in available:
                _CACHED_MONO_FAMILY = fam
                return fam
    except Exception:
        pass
    _CACHED_MONO_FAMILY = "monospace"
    return _CACHED_MONO_FAMILY


def get_font(size: int = 10, weight: str = "normal", slant: str = "roman") -> Tuple[str, int, str]:
    """Trả về cấu hình phông sans-serif chuẩn."""
    return (resolve_sans_family(), size, weight)


def get_mono_font(size: int = 9, weight: str = "normal") -> Tuple[str, int, str]:
    """Trả về cấu hình phông monospace chuẩn."""
    return (resolve_mono_family(), size, weight)


# ============================================================================
# Quản lý Chấm Trạng thái Thiết bị (Status Dots)
# ============================================================================
def _create_circle_photo_image(hex_color: str, size: int = 16) -> tk.PhotoImage:
    """Vẽ một chấm tròn mượt (anti-aliased) trực tiếp vào tk.PhotoImage."""
    img = tk.PhotoImage(width=size, height=size)
    c = (size - 1) / 2.0
    r_core = (size / 2.0) - 2.0
    r_core_sq = r_core * r_core
    r_outer_sq = (r_core + 0.8) * (r_core + 0.8)

    for y in range(size):
        dy = y - c
        for x in range(size):
            dx = x - c
            dist_sq = dx * dx + dy * dy
            if dist_sq <= r_core_sq:
                img.put(hex_color, (x, y))
            elif dist_sq <= r_outer_sq:
                img.put(hex_color, (x, y))
    return img


class StatusDotRegistry:
    """Bộ nhớ cache lưu các PhotoImage chấm trạng thái."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._cache: Dict[str, tk.PhotoImage] = {}
        self._load_all()

    def _load_all(self) -> None:
        mapping = {
            "online": (ASSETS_DIR / "dot-online.png", STATUS_ONLINE),
            "running": (ASSETS_DIR / "dot-running.png", STATUS_RUNNING),
            "unauthorized": (ASSETS_DIR / "dot-unauthorized.png", STATUS_UNAUTHORIZED),
            "offline": (ASSETS_DIR / "dot-offline.png", STATUS_OFFLINE),
        }

        for name, (asset_path, color_hex) in mapping.items():
            loaded = None
            if asset_path.is_file():
                try:
                    loaded = tk.PhotoImage(file=str(asset_path))
                except Exception:
                    loaded = None
            if loaded is None:
                try:
                    loaded = _create_circle_photo_image(color_hex, size=16)
                except Exception:
                    loaded = None
            if loaded:
                self._cache[name] = loaded

    def get(self, status_key: str) -> Optional[tk.PhotoImage]:
        """Lấy PhotoImage tương ứng với trạng thái thiết bị."""
        key = status_key.lower()
        if "run" in key or "hiển thị" in key:
            return self._cache.get("running")
        if key in ("device", "online", "sẵn sàng"):
            return self._cache.get("online")
        if "unauthorized" in key or "authorizing" in key or "quyền" in key:
            return self._cache.get("unauthorized")
        return self._cache.get("offline")


# ============================================================================
# Thành phần Khung dạng Thẻ (Card Container)
# ============================================================================
class Card(tk.Frame):
    """Khung dạng thẻ hiện đại với nền tối nổi, viền tinh tế và đệm thoáng."""

    def __init__(
        self,
        master: tk.Widget,
        padding: Tuple[int, int] = (14, 12),
        border_color: str = BORDER,
        bg_color: str = BG_CARD,
        **kwargs,
    ):
        super().__init__(
            master,
            bg=bg_color,
            highlightbackground=border_color,
            highlightcolor=border_color,
            highlightthickness=1,
            padx=padding[0],
            pady=padding[1],
            **kwargs,
        )
        self.bg_color = bg_color

    def add_header(
        self,
        title: str,
        subtitle: str = "",
        badge_text: str = "",
    ) -> Tuple[tk.Label, Optional[tk.Label], Optional[tk.Label]]:
        """Tạo thanh tiêu đề cho thẻ."""
        header_frame = tk.Frame(self, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_lbl = tk.Label(
            header_frame,
            text=title,
            bg=self.bg_color,
            fg=TEXT_PRIMARY,
            font=get_font(11, "bold"),
        )
        title_lbl.pack(side=tk.LEFT)

        sub_lbl = None
        if subtitle:
            sub_lbl = tk.Label(
                header_frame,
                text=subtitle,
                bg=self.bg_color,
                fg=TEXT_SECONDARY,
                font=get_font(9),
            )
            sub_lbl.pack(side=tk.LEFT, padx=(8, 0))

        badge_lbl = None
        if badge_text:
            badge_lbl = tk.Label(
                header_frame,
                text=badge_text,
                bg=BADGE_BG,
                fg=BADGE_FG,
                font=get_font(8, "bold"),
                padx=8,
                pady=2,
            )
            badge_lbl.pack(side=tk.RIGHT)

        return title_lbl, sub_lbl, badge_lbl


# ============================================================================
# Cấu hình Giao diện ttk (Apply Theme)
# ============================================================================
def apply_theme(root: tk.Tk) -> StatusDotRegistry:
    """Cấu hình toàn bộ chủ đề tối hiện đại cho root và ttk."""
    root.configure(bg=BG_DARK)

    # Đăng ký màu sắc cho hộp dropdown Combobox
    root.option_add("*TCombobox*Listbox.background", BG_CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", get_font(9))

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    font_base = get_font(10)
    font_bold = get_font(9, "bold")
    font_small = get_font(9)

    # 1. Khung (Frame)
    style.configure("TFrame", background=BG_DARK)
    style.configure("Card.TFrame", background=BG_CARD)

    # 2. Nhãn (Label)
    style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY, font=font_base)
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY, font=font_base)
    style.configure("CardTitle.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY, font=get_font(11, "bold"))
    style.configure("Muted.TLabel", background=BG_CARD, foreground=TEXT_SECONDARY, font=font_small)

    # 3. Nút hành động chính (Accent / Hiển thị)
    style.configure(
        "Accent.TButton",
        background=ACCENT_BG,
        foreground=ACCENT_FG,
        font=font_bold,
        bordercolor=ACCENT_BG,
        lightcolor=ACCENT_BG,
        darkcolor=ACCENT_BG,
        focuscolor=ACCENT_BG,
        padding=(14, 7),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", BTN_DISABLED_BG),
            ("pressed", ACCENT_PRESSED),
            ("active", ACCENT_HOVER),
        ],
        foreground=[("disabled", BTN_DISABLED_FG), ("active", "#ffffff")],
        bordercolor=[("disabled", BTN_DISABLED_BORDER), ("active", ACCENT_HOVER)],
    )

    # 4. Nút nguy hiểm (Danger / Dừng)
    style.configure(
        "Danger.TButton",
        background=DANGER_BG,
        foreground=DANGER_FG,
        font=font_bold,
        bordercolor=DANGER_BG,
        lightcolor=DANGER_BG,
        darkcolor=DANGER_BG,
        focuscolor=DANGER_BG,
        padding=(14, 7),
    )
    style.map(
        "Danger.TButton",
        background=[
            ("disabled", BTN_DISABLED_BG),
            ("pressed", DANGER_PRESSED),
            ("active", DANGER_HOVER),
        ],
        foreground=[("disabled", BTN_DISABLED_FG), ("active", "#ffffff")],
        bordercolor=[("disabled", BTN_DISABLED_BORDER), ("active", DANGER_HOVER)],
    )

    # 5. Nút phụ (Secondary / Làm mới, Wi-Fi)
    style.configure(
        "Secondary.TButton",
        background=BTN_SEC_BG,
        foreground=BTN_SEC_FG,
        font=font_small,
        bordercolor=BTN_SEC_BORDER,
        lightcolor=BTN_SEC_BORDER,
        darkcolor=BTN_SEC_BORDER,
        focuscolor=BORDER_FOCUS,
        padding=(10, 5),
    )
    style.map(
        "Secondary.TButton",
        background=[
            ("disabled", BTN_DISABLED_BG),
            ("pressed", BTN_SEC_PRESSED),
            ("active", BTN_SEC_HOVER),
        ],
        foreground=[("disabled", BTN_DISABLED_FG), ("active", "#ffffff")],
        bordercolor=[("disabled", BTN_DISABLED_BORDER), ("active", BTN_SEC_BORDER)],
    )

    # 6. Bảng danh sách thiết bị (Treeview)
    style.configure(
        "Treeview",
        background=BG_INPUT,
        foreground=TEXT_PRIMARY,
        fieldbackground=BG_INPUT,
        rowheight=32,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        font=font_base,
    )
    style.map(
        "Treeview",
        background=[
            ("selected focus", ACCENT_BG),
            ("selected", "#22334d"),
        ],
        foreground=[("selected", "#ffffff")],
    )

    style.configure(
        "Treeview.Heading",
        background=BG_CARD_HEADER,
        foreground=TEXT_SECONDARY,
        bordercolor=BORDER,
        relief="flat",
        font=font_bold,
        padding=(8, 7),
    )
    style.map("Treeview.Heading", background=[("active", "#222d3d")])

    # 7. Hộp chọn (Combobox)
    style.configure(
        "TCombobox",
        background=BTN_SEC_BG,
        fieldbackground=BG_INPUT,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER,
        arrowcolor=TEXT_SECONDARY,
        padding=5,
        font=font_small,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", BORDER_FOCUS)],
        fieldbackground=[("readonly", BG_INPUT)],
    )

    # 8. Hộp đánh dấu (Checkbutton)
    style.configure(
        "TCheckbutton",
        background=BG_CARD,
        foreground=TEXT_PRIMARY,
        indicatorbackground=BG_INPUT,
        indicatorcolor=ACCENT_BG,
        bordercolor=BORDER,
        font=font_small,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_CARD)],
        indicatorbackground=[("active", "#1e2636")],
    )

    # 9. Ô nhập văn bản (Entry)
    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        foreground=TEXT_PRIMARY,
        insertcolor=TEXT_PRIMARY,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=6,
        font=font_small,
    )
    style.map("TEntry", bordercolor=[("focus", BORDER_FOCUS)])

    # 10. Thanh cuộn (Scrollbar)
    style.configure(
        "TScrollbar",
        background=BORDER,
        troughcolor=BG_INPUT,
        bordercolor=BG_INPUT,
        arrowcolor=TEXT_SECONDARY,
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", BORDER_FOCUS)])

    return StatusDotRegistry(root)
