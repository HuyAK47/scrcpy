"""Kiểm tra module theme: bảng màu, phông chữ, chấm trạng thái và Card."""

import os
import re
import unittest
from pathlib import Path

from scrcpy_gui import theme

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TestThemePalette(unittest.TestCase):
    """Kiểm tra bảng màu chủ đề tối."""

    def test_colors_are_valid_hex(self):
        colors = [
            theme.BG_DARK,
            theme.BG_CARD,
            theme.BG_CARD_HEADER,
            theme.BG_INPUT,
            theme.BORDER,
            theme.BORDER_FOCUS,
            theme.TEXT_PRIMARY,
            theme.TEXT_SECONDARY,
            theme.TEXT_MUTED,
            theme.ACCENT_BG,
            theme.ACCENT_HOVER,
            theme.ACCENT_PRESSED,
            theme.ACCENT_FG,
            theme.DANGER_BG,
            theme.DANGER_HOVER,
            theme.DANGER_PRESSED,
            theme.DANGER_FG,
            theme.BTN_SEC_BG,
            theme.BTN_SEC_HOVER,
            theme.BTN_SEC_PRESSED,
            theme.BTN_SEC_BORDER,
            theme.BTN_SEC_FG,
            theme.BTN_DISABLED_BG,
            theme.BTN_DISABLED_FG,
            theme.BTN_DISABLED_BORDER,
            theme.STATUS_ONLINE,
            theme.STATUS_RUNNING,
            theme.STATUS_UNAUTHORIZED,
            theme.STATUS_OFFLINE,
            theme.BANNER_WARN_BG,
            theme.BANNER_WARN_BORDER,
            theme.BANNER_WARN_FG,
            theme.BADGE_BG,
            theme.BADGE_FG,
        ]
        for c in colors:
            with self.subTest(color=c):
                self.assertIsNotNone(
                    HEX_COLOR_RE.match(c),
                    f"Mã màu không hợp lệ: {c}",
                )

    def test_font_helpers_return_tuples(self):
        sans_font = theme.get_font(12, "bold")
        self.assertEqual(len(sans_font), 3)
        self.assertIsInstance(sans_font[0], str)
        self.assertEqual(sans_font[1], 12)
        self.assertEqual(sans_font[2], "bold")

        mono_font = theme.get_mono_font(9)
        self.assertEqual(len(mono_font), 3)
        self.assertIsInstance(mono_font[0], str)
        self.assertEqual(mono_font[1], 9)
        self.assertEqual(mono_font[2], "normal")

    def test_assets_exist(self):
        for name in ("dot-online.png", "dot-running.png", "dot-unauthorized.png", "dot-offline.png"):
            with self.subTest(asset=name):
                p = theme.ASSETS_DIR / name
                self.assertTrue(p.is_file(), f"Thiếu asset: {p}")


class TestThemeTk(unittest.TestCase):
    """Kiểm tra áp dụng theme trên môi trường có DISPLAY."""

    def setUp(self):
        if not os.environ.get("DISPLAY"):
            self.skipTest("Bỏ qua kiểm tra GUI do không có DISPLAY")
        import tkinter as tk
        self.tk = tk
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError:
            self.skipTest("Không khởi tạo được Tk root")

    def tearDown(self):
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_apply_theme_and_dot_registry(self):
        registry = theme.apply_theme(self.root)
        self.assertIsNotNone(registry)
        self.assertEqual(self.root.cget("bg"), theme.BG_DARK)

        # Kiểm tra nạp chấm trạng thái
        for state in ("device", "online", "running", "unauthorized", "offline", "unknown"):
            with self.subTest(state=state):
                img = registry.get(state)
                self.assertIsNotNone(img, f"Không nạp được chấm trạng thái cho {state}")
                self.assertEqual(img.width(), 16)
                self.assertEqual(img.height(), 16)

    def test_card_widget(self):
        theme.apply_theme(self.root)
        card = theme.Card(self.root)
        card.pack()
        title_lbl, sub_lbl, badge_lbl = card.add_header(
            title="Tiêu đề thử",
            subtitle="Phụ đề",
            badge_text="2 mục",
        )
        self.assertEqual(title_lbl.cget("text"), "Tiêu đề thử")
        self.assertIsNotNone(sub_lbl)
        self.assertEqual(sub_lbl.cget("text"), "Phụ đề")
        self.assertIsNotNone(badge_lbl)
        self.assertEqual(badge_lbl.cget("text"), "2 mục")
        self.root.update()


    def test_notebook_widget(self):
        theme.apply_theme(self.root)
        from tkinter import ttk
        nb = ttk.Notebook(self.root)
        nb.pack()
        f1 = ttk.Frame(nb)
        f2 = ttk.Frame(nb)
        nb.add(f1, text="Thiết bị")
        nb.add(f2, text="Xem trước")
        self.root.update()
        self.assertEqual(len(nb.tabs()), 2)


if __name__ == "__main__":
    unittest.main()
