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
             patch("scrcpy_gui.app.load_settings", return_value=settings.Settings()), \
             patch("scrcpy_gui.app.save_settings"), \
             patch.object(app.ScrcpyApp, "_init_timer"):
            self.gui = app.ScrcpyApp(self.root)

    def tearDown(self):
        if hasattr(self, "gui") and self.gui:
            self.gui._closing = True
            if hasattr(self.gui, "preview_manager"):
                self.gui.preview_manager.cancel_all()
            if hasattr(self.gui, "live_launcher"):
                self.gui.live_launcher.stop_all()
            if hasattr(self.gui, "launcher"):
                self.gui.launcher.stop_all()
            if getattr(self.gui, "_preview_timer_id", None):
                try:
                    self.gui.root.after_cancel(self.gui._preview_timer_id)
                except Exception:
                    pass
        if hasattr(self, "root") and self.root:
            try:
                self.root.update_idletasks()
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

    def test_notebook_and_preview_widgets_initialized(self):
        """Kiểm tra ttk.Notebook và các widget trong tab Xem trước đã được tạo đầy đủ."""
        self.assertIsNotNone(self.gui.notebook)
        self.assertIsNotNone(self.gui.tab_devices)
        self.assertIsNotNone(self.gui.tab_preview)
        self.assertIsNotNone(self.gui.chk_preview_enabled)
        self.assertIsNotNone(self.gui.cb_preview_interval)
        self.assertIsNotNone(self.gui.btn_live_tiling)
        self.assertIsNotNone(self.gui.preview_canvas)
        self.assertIsNotNone(self.gui.preview_grid_frame)

        tab_names = [self.gui.notebook.tab(i, "text") for i in range(2)]
        self.assertEqual(tab_names, ["Thiết bị", "Xem trước"])

    def test_preview_disabled_by_default_and_does_not_capture(self):
        """Mặc định preview tắt, không chạy lệnh chụp nào."""
        self.assertFalse(self.gui.var_preview_enabled.get())
        self.assertFalse(self.gui._is_preview_active())

        dev = adb.DeviceInfo(
            serial="dev_test_1",
            state="device",
            model="Pixel 6",
            product="pixel6",
            device="oriole",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev])

        with patch.object(self.gui.preview_manager, "start_capture") as mock_capture:
            self.gui._preview_tick()
            mock_capture.assert_not_called()

        # Ô preview hiển thị placeholder tắt
        card = self.gui._preview_cards["dev_test_1"]
        self.assertIn("Xem trước đang tắt", card.lbl_image.cget("text"))

    def test_preview_toggle_and_tab_switching(self):
        """Bật công tắc và đổi tab sẽ tạm dừng / kích hoạt lại preview manager."""
        # Chuyển sang tab Xem trước
        self.gui.notebook.select(self.gui.tab_preview)
        self.gui._on_tab_changed()

        # Bật công tắc preview
        self.gui.var_preview_enabled.set(True)
        self.gui._on_preview_toggle()

        self.assertTrue(self.gui.preview_manager.is_enabled)
        self.assertTrue(self.gui._is_preview_active())

        # Chuyển về tab Thiết bị -> preview manager tạm dừng
        self.gui.notebook.select(self.gui.tab_devices)
        self.gui._on_tab_changed()

        self.assertFalse(self.gui.preview_manager.is_enabled)
        self.assertFalse(self.gui._is_preview_active())

    def test_preview_cards_population_and_double_click(self):
        """Đồng bộ thẻ thiết bị và kiểm tra mở scrcpy qua double-click hoặc nút Mở."""
        dev_ready = adb.DeviceInfo(
            serial="dev_ready",
            state="device",
            model="Galaxy S22",
            product="s22",
            device="s22",
            transport="usb",
        )
        dev_unauth = adb.DeviceInfo(
            serial="dev_unauth",
            state="unauthorized",
            model="",
            product="",
            device="",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev_ready, dev_unauth])

        self.assertEqual(len(self.gui._preview_cards), 2)
        card_ready = self.gui._preview_cards["dev_ready"]
        card_unauth = self.gui._preview_cards["dev_unauth"]

        self.assertEqual(str(card_ready.btn_open.cget("state")), "normal")
        self.assertEqual(str(card_unauth.btn_open.cget("state")), "disabled")
        self.assertIn("Chưa cho phép", card_unauth.lbl_image.cget("text"))

        # Double click ô dev_ready
        with patch.object(self.gui.launcher, "start") as mock_start:
            self.gui._on_preview_card_double_click(dev_ready)
            mock_start.assert_called_once_with(
                serial="dev_ready",
                model="Galaxy S22",
                settings=self.gui.settings,
            )

        # Double click ô unauthorized không chạy
        with patch.object(self.gui.launcher, "start") as mock_start:
            self.gui._on_preview_card_double_click(dev_unauth)
            mock_start.assert_not_called()

        # Nếu đã đang chạy scrcpy thì double click không mở thêm
        with patch.object(self.gui.launcher, "is_running", return_value=True), \
             patch.object(self.gui.launcher, "start") as mock_start:
            self.gui._on_preview_card_double_click(dev_ready)
            mock_start.assert_not_called()

    def test_preview_card_error_handling_preserves_photo(self):
        """Lỗi chụp hiển thị thông báo ngắn và giữ ảnh cũ nếu có."""
        dev = adb.DeviceInfo(
            serial="dev_err",
            state="device",
            model="Pixel",
            product="p",
            device="p",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev])
        card = self.gui._preview_cards["dev_err"]

        # Giả lập đã có ảnh trước đó
        dummy_photo = MagicMock()
        card.current_photo = dummy_photo

        self.gui._apply_preview_error("dev_err", "Hết thời gian chụp màn hình (8.0s)")
        self.assertEqual(card.current_photo, dummy_photo)
        self.assertIn("Hết thời gian", card.lbl_error.cget("text"))

    def test_live_tiling_toggle(self):
        """Bật và tắt chế độ Xếp lưới live."""
        dev1 = adb.DeviceInfo(
            serial="dev1",
            state="device",
            model="Model 1",
            product="m1",
            device="m1",
            transport="usb",
        )
        dev_offline = adb.DeviceInfo(
            serial="dev_off",
            state="offline",
            model="",
            product="",
            device="",
            transport="usb",
        )
        self.gui._on_device_list_ready([dev1, dev_offline])

        with patch.object(self.gui.live_launcher, "start") as mock_start:
            self.gui._on_toggle_live_tiling()
            # Chỉ mở cho dev1 ở trạng thái device
            mock_start.assert_called_once()
            self.assertEqual(mock_start.call_args[1]["serial"], "dev1")
            custom_cmd = mock_start.call_args[1]["custom_cmd"]
            self.assertIn("--no-control", custom_cmd)
            self.assertIn("--window-title", custom_cmd)
            self.assertEqual(self.gui.btn_live_tiling.cget("text"), "✕  Đóng lưới live")

        # Bấm lần nữa để đóng lưới live
        with patch.object(self.gui.live_launcher, "has_active_sessions", return_value=True), \
             patch.object(self.gui.live_launcher, "stop_all") as mock_stop:
            self.gui._on_toggle_live_tiling()
            mock_stop.assert_called_once()
            self.assertEqual(self.gui.btn_live_tiling.cget("text"), "⊞  Xếp lưới live")


if __name__ == "__main__":
    unittest.main()
