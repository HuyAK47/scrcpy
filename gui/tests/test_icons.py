"""Kiểm tra icon của app và icon cửa sổ hiển thị màn hình."""

import struct
import unittest
from pathlib import Path

from scrcpy_gui import app

_ASSETS = Path(app.__file__).resolve().parent / "assets"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_size(path: Path):
    data = path.read_bytes()[:24]
    if not data.startswith(_PNG_SIGNATURE):
        return None
    return struct.unpack(">II", data[16:24])


class TestIcons(unittest.TestCase):
    def test_icons_are_256_png(self):
        for name in ("app-icon.png", "screen-icon.png"):
            with self.subTest(icon=name):
                self.assertEqual(_png_size(_ASSETS / name), (256, 256))

    def test_app_and_screen_icons_differ(self):
        self.assertNotEqual(
            (_ASSETS / "app-icon.png").read_bytes(),
            (_ASSETS / "screen-icon.png").read_bytes(),
        )

    def test_app_icon_path_points_to_asset(self):
        self.assertEqual(app.APP_ICON_PATH, _ASSETS / "app-icon.png")

    def test_set_window_icon_missing_file_returns_false(self):
        self.assertFalse(app.set_window_icon(None, _ASSETS / "khong-ton-tai.png"))


if __name__ == "__main__":
    unittest.main()
