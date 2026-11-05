"""Unit tests cho ScrcpyApp và các thành phần giao diện."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scrcpy_gui import adb, app, settings


class TestScrcpyApp(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("DISPLAY"):
            self.skipTest("Bỏ qua kiểm tra GUI do không có DISPLAY")
        import tkinter as tk
        try:
            self.root = tk.Tk(className=app.WM_CLASS_NAME)
            self.root.withdraw()
        except tk.TclError:
            self.skipTest("Không thể khởi tạo Tk root")

        # Mock find_adb và find_scrcpy để tránh phụ thuộc môi trường
        with patch("scrcpy_gui.app.find_adb", return_value="/mock/adb"), \
             patch("scrcpy_gui.app.find_scrcpy", return_value="/mock/scrcpy"), \
             patch.object(app.ScrcpyApp, "_init_timer"):
            self.gui = app.ScrcpyApp(self.root)

    def tearDown(self):
        if hasattr(self, "gui") and self.gui:
            self.gui._closing = True
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_widgets_initialized(self):
        """Kiểm tra các widget chính đã được khởi tạo đầy đủ."""
        self.assertIsNotNone(self.gui.tree)
        self.assertIsNotNone(self.gui.btn_start)
        self.assertIsNotNone(self.gui.btn_stop)
        self.assertIsNotNone(self.gui.btn_refresh)
        self.assertIsNotNone(self.gui.btn_connect)
        self.assertIsNotNone(self.gui.btn_switch_wifi)
        self.assertIsNotNone(self.gui.btn_disconnect)
        self.assertIsNotNone(self.gui.lbl_device_count)
        self.assertIsNotNone(self.gui.lbl_status)
        self.assertIsNotNone(self.gui.wifi_entry)

    def test_device_list_ready_populates_tree_and_badge(self):
        """Cập nhật danh sách thiết bị hiển thị đúng dòng và số lượng."""
        dev = adb.DeviceInfo(
            serial="emulator-5554",
            state="device",
            model="Android SDK built for x86",
            product="sdk_gphone64_x86_64",
            device="emu64x",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev])
        self.assertEqual(self.gui.lbl_device_count.cget("text"), "1 thiết bị")

        children = self.gui.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], "emulator-5554")

        vals = self.gui.tree.item("emulator-5554", "values")
        self.assertEqual(vals[0], dev.display_model)
        self.assertEqual(vals[1], "emulator-5554")
        self.assertEqual(vals[2], "USB")
        self.assertEqual(vals[3], "Sẵn sàng")

    def test_button_states_usb_device(self):
        """Kiểm tra trạng thái nút khi chọn thiết bị USB ở trạng thái device."""
        dev = adb.DeviceInfo(
            serial="usb-1234",
            state="device",
            model="Pixel 6",
            product="pixel6",
            device="oriole",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev])
        self.gui.tree.selection_set("usb-1234")
        self.gui._update_button_states()

        # Start bật, Switch Wi-Fi bật, Stop tắt, Disconnect tắt
        self.assertEqual(str(self.gui.btn_start.cget("state")), "normal")
        self.assertEqual(str(self.gui.btn_switch_wifi.cget("state")), "normal")
        self.assertEqual(str(self.gui.btn_stop.cget("state")), "disabled")
        self.assertEqual(str(self.gui.btn_disconnect.cget("state")), "disabled")

    def test_button_states_wifi_device(self):
        """Kiểm tra trạng thái nút khi chọn thiết bị Wi-Fi."""
        dev = adb.DeviceInfo(
            serial="192.168.1.42:5555",
            state="device",
            model="Pixel 7",
            product="pixel7",
            device="cheetah",
            transport="wifi",
        )
        self.gui._on_device_list_ready([dev])
        self.gui.tree.selection_set("192.168.1.42:5555")
        self.gui._update_button_states()

        # Start bật, Disconnect bật, Switch Wi-Fi tắt
        self.assertEqual(str(self.gui.btn_start.cget("state")), "normal")
        self.assertEqual(str(self.gui.btn_disconnect.cget("state")), "normal")
        self.assertEqual(str(self.gui.btn_switch_wifi.cget("state")), "disabled")

    def test_status_update(self):
        """Kiểm tra cập nhật thanh trạng thái."""
        self.gui._set_status("Đang kiểm tra kết nối...")
        self.assertIn("Đang kiểm tra kết nối...", self.gui.lbl_status.cget("text"))


if __name__ == "__main__":
    unittest.main()
