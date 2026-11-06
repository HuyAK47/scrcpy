"""Unit tests cho module preview: kích thước PNG, subsample factor, screencap, guard, live tile."""

import math
import subprocess
import sys
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Thêm thư mục gui vào sys.path
_gui_dir = str(Path(__file__).resolve().parent.parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from scrcpy_gui.preview import (
    PreviewCaptureError,
    PreviewManager,
    build_live_command,
    capture_screenshot,
    compute_subsample_factor,
    compute_tile_geometry,
    parse_png_dimensions,
)


def _make_dummy_png(width: int = 1080, height: int = 2400) -> bytes:
    """Tạo dữ liệu PNG tối thiểu có header và khối IHDR với kích thước mong muốn."""
    header = b"\x89PNG\r\n\x1a\n"
    ihdr_len = b"\x00\x00\x00\r"
    ihdr_type = b"IHDR"
    w_bytes = width.to_bytes(4, "big")
    h_bytes = height.to_bytes(4, "big")
    rest = b"\x08\x06\x00\x00\x00\x00\x00\x00\x00"
    return header + ihdr_len + ihdr_type + w_bytes + h_bytes + rest


class TestPreviewFunctions(unittest.TestCase):
    def test_parse_png_dimensions_valid(self):
        png = _make_dummy_png(1080, 2400)
        w, h = parse_png_dimensions(png)
        self.assertEqual(w, 1080)
        self.assertEqual(h, 2400)

        png_small = _make_dummy_png(720, 1280)
        w2, h2 = parse_png_dimensions(png_small)
        self.assertEqual(w2, 720)
        self.assertEqual(h2, 1280)

    def test_parse_png_dimensions_invalid(self):
        with self.assertRaises(PreviewCaptureError):
            parse_png_dimensions(b"too short")

        with self.assertRaises(PreviewCaptureError):
            parse_png_dimensions(b"01234567890123456789012345")  # Not PNG

        corrupted = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rNOPE" + (100).to_bytes(4, "big") + (100).to_bytes(4, "big")
        with self.assertRaises(PreviewCaptureError):
            parse_png_dimensions(corrupted)

    def test_compute_subsample_factor(self):
        # Ảnh nhỏ hơn hoặc bằng khung mục tiêu -> hệ số là 1
        self.assertEqual(compute_subsample_factor(200, 300, 200, 300), 1)
        self.assertEqual(compute_subsample_factor(100, 100, 200, 300), 1)

        # Kích thước không hợp lệ -> fallback 1
        self.assertEqual(compute_subsample_factor(0, 100, 200, 200), 1)
        self.assertEqual(compute_subsample_factor(100, 0, 200, 200), 1)
        self.assertEqual(compute_subsample_factor(100, 100, -1, 200), 1)

        # 1080x2400 mục tiêu 240x360:
        # factor_w = 1080/240 = 4.5; factor_h = 2400/360 = 6.666...
        # max = 6.666...; ceil = 7
        self.assertEqual(compute_subsample_factor(1080, 2400, 240, 360), 7)

        # 1000x500 mục tiêu 500x500:
        # factor_w = 2.0; factor_h = 1.0 -> 2
        self.assertEqual(compute_subsample_factor(1000, 500, 500, 500), 2)

    def test_compute_tile_geometry(self):
        # 1 cửa sổ chiếm toàn màn hình
        self.assertEqual(compute_tile_geometry(0, 1, 1920, 1080), (0, 0, 1920, 1080))
        self.assertEqual(compute_tile_geometry(0, 0, 1920, 1080), (0, 0, 1920, 1080))

        # 4 cửa sổ xếp 2x2
        # cols = ceil(sqrt(4)) = 2, rows = ceil(4/2) = 2
        # tile_w = 960, tile_h = 540
        self.assertEqual(compute_tile_geometry(0, 4, 1920, 1080), (0, 0, 960, 540))
        self.assertEqual(compute_tile_geometry(1, 4, 1920, 1080), (960, 0, 960, 540))
        self.assertEqual(compute_tile_geometry(2, 4, 1920, 1080), (0, 540, 960, 540))
        self.assertEqual(compute_tile_geometry(3, 4, 1920, 1080), (960, 540, 960, 540))

        # 6 cửa sổ: cols = ceil(sqrt(6)) = 3, rows = ceil(6/3) = 2
        # screen 1800x900 -> tile_w = 600, tile_h = 450
        self.assertEqual(compute_tile_geometry(0, 6, 1800, 900), (0, 0, 600, 450))
        self.assertEqual(compute_tile_geometry(2, 6, 1800, 900), (1200, 0, 600, 450))
        self.assertEqual(compute_tile_geometry(3, 6, 1800, 900), (0, 450, 600, 450))
        self.assertEqual(compute_tile_geometry(5, 6, 1800, 900), (1200, 450, 600, 450))

    def test_build_live_command(self):
        cmd = build_live_command(
            serial="serial_test",
            model="Galaxy S22",
            geometry=(100, 200, 400, 800),
            scrcpy_bin="/custom/scrcpy",
        )
        self.assertEqual(cmd[0], "/custom/scrcpy")
        self.assertEqual(cmd[1], "-s")
        self.assertEqual(cmd[2], "serial_test")
        self.assertIn("--window-title", cmd)
        idx_title = cmd.index("--window-title")
        self.assertEqual(cmd[idx_title + 1], "Galaxy S22 (serial_test) [live]")
        self.assertIn("--no-control", cmd)
        self.assertIn("--no-audio", cmd)
        self.assertIn("--window-borderless", cmd)
        self.assertIn("--max-size", cmd)
        self.assertEqual(cmd[cmd.index("--max-size") + 1], "360")
        self.assertIn("--max-fps", cmd)
        self.assertEqual(cmd[cmd.index("--max-fps") + 1], "10")
        self.assertIn("--video-bit-rate", cmd)
        self.assertEqual(cmd[cmd.index("--video-bit-rate") + 1], "1M")

        self.assertIn("--window-x", cmd)
        self.assertEqual(cmd[cmd.index("--window-x") + 1], "100")
        self.assertIn("--window-y", cmd)
        self.assertEqual(cmd[cmd.index("--window-y") + 1], "200")
        self.assertIn("--window-width", cmd)
        self.assertEqual(cmd[cmd.index("--window-width") + 1], "400")
        self.assertIn("--window-height", cmd)
        self.assertEqual(cmd[cmd.index("--window-height") + 1], "800")


class TestCaptureScreenshot(unittest.TestCase):
    @patch("subprocess.Popen")
    def test_capture_success(self, mock_popen):
        dummy_png = _make_dummy_png(720, 1280)
        proc = MagicMock()
        proc.communicate.return_value = (dummy_png, b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        result = capture_screenshot("dev_123", adb_bin="adb")
        self.assertEqual(result, dummy_png)
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        self.assertEqual(cmd, ["adb", "-s", "dev_123", "exec-out", "screencap", "-p"])

    @patch("subprocess.Popen")
    def test_capture_timeout(self, mock_popen):
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="screencap", timeout=2.0)
        mock_popen.return_value = proc

        with self.assertRaises(PreviewCaptureError) as ctx:
            capture_screenshot("dev_123", adb_bin="adb", timeout=2.0)
        self.assertIn("Hết thời gian", str(ctx.exception))
        proc.kill.assert_called_once()

    @patch("subprocess.Popen")
    def test_capture_error_returncode(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"device offline\n")
        proc.returncode = 1
        mock_popen.return_value = proc

        with self.assertRaises(PreviewCaptureError) as ctx:
            capture_screenshot("dev_123", adb_bin="adb")
        self.assertIn("device offline", str(ctx.exception))

    @patch("subprocess.Popen")
    def test_capture_invalid_png_data(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = (b"Error: permission denied", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        with self.assertRaises(PreviewCaptureError) as ctx:
            capture_screenshot("dev_123", adb_bin="adb")
        self.assertIn("không hợp lệ", str(ctx.exception))


class TestPreviewManager(unittest.TestCase):
    def test_disabled_by_default_rejects_captures(self):
        mgr = PreviewManager(adb_bin="adb")
        self.assertFalse(mgr.is_enabled)
        scheduled = mgr.start_capture("dev1", on_success=MagicMock(), on_error=MagicMock())
        self.assertFalse(scheduled)
        self.assertFalse(mgr.is_capturing("dev1"))

    @patch("subprocess.Popen")
    def test_single_command_guard_prevents_overlap(self, mock_popen):
        dummy_png = _make_dummy_png(100, 100)
        proc = MagicMock()
        # Giả lập lệnh chụp chạy chậm
        def slow_communicate(timeout=None):
            time.sleep(0.15)
            return (dummy_png, b"")

        proc.communicate.side_effect = slow_communicate
        proc.returncode = 0
        mock_popen.return_value = proc

        mgr = PreviewManager(adb_bin="adb")
        mgr.set_enabled(True)

        on_success = MagicMock()
        on_error = MagicMock()

        # Lệnh đầu tiên được chấp nhận
        first = mgr.start_capture("dev1", on_success=on_success, on_error=on_error)
        self.assertTrue(first)
        self.assertTrue(mgr.is_capturing("dev1"))

        # Lệnh thứ hai cho cùng 1 serial trong khi lệnh 1 đang chạy -> bị từ chối (guard 1 lệnh/thiết bị)
        second = mgr.start_capture("dev1", on_success=on_success, on_error=on_error)
        self.assertFalse(second)

        # Chờ lệnh 1 hoàn tất
        time.sleep(0.3)
        self.assertFalse(mgr.is_capturing("dev1"))
        on_success.assert_called_once_with("dev1", dummy_png)
        on_error.assert_not_called()
        mgr.cancel_all()

    @patch("subprocess.Popen")
    def test_disabling_cancels_and_stops_captures(self, mock_popen):
        started_event = threading.Event()
        proc = MagicMock()

        def fake_communicate(timeout=None):
            started_event.set()
            time.sleep(0.5)
            return (b"", b"")

        proc.communicate.side_effect = fake_communicate
        proc.returncode = 0
        mock_popen.return_value = proc

        mgr = PreviewManager(adb_bin="adb")
        mgr.set_enabled(True)

        on_success = MagicMock()
        on_error = MagicMock()

        mgr.start_capture("dev1", on_success=on_success, on_error=on_error)
        started_event.wait(timeout=2.0)

        # Tắt giữa chừng
        mgr.set_enabled(False)
        self.assertFalse(mgr.is_enabled)
        proc.kill.assert_called()

        time.sleep(0.1)
        on_success.assert_not_called()
        on_error.assert_not_called()

    @patch("subprocess.Popen")
    def test_capture_error_calls_error_callback(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"device not found")
        proc.returncode = 1
        mock_popen.return_value = proc

        mgr = PreviewManager(adb_bin="adb")
        mgr.set_enabled(True)

        on_success = MagicMock()
        on_error = MagicMock()

        mgr.start_capture("dev_err", on_success=on_success, on_error=on_error)
        time.sleep(0.1)

        on_success.assert_not_called()
        on_error.assert_called_once()
        self.assertIn("dev_err", on_error.call_args[0][0])
        self.assertIn("device not found", on_error.call_args[0][1])
        mgr.cancel_all()


if __name__ == "__main__":
    unittest.main()
