"""Unit tests for adb command execution and parsing."""

import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Add gui directory to sys.path
_gui_dir = str(Path(__file__).resolve().parent.parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from scrcpy_gui.adb import (
    DeviceInfo,
    classify_transport,
    connect_wifi,
    disconnect_wifi,
    list_devices,
    parse_devices_output,
    parse_ip_route,
    switch_to_wifi,
)


class TestAdb(unittest.TestCase):
    def test_classify_transport(self):
        # Wi-Fi cases
        self.assertEqual(classify_transport("192.168.1.100:5555"), "wifi")
        self.assertEqual(classify_transport("10.0.0.12:4444"), "wifi")
        self.assertEqual(classify_transport("device._adb-tls-connect._tcp"), "wifi")
        self.assertEqual(classify_transport("adb-12345._adb-tls-connect._tcp."), "wifi")

        # USB cases
        self.assertEqual(classify_transport("0123456789ABCDEF"), "usb")
        self.assertEqual(classify_transport("emulator-5554"), "usb")
        self.assertEqual(classify_transport("R58M43XYZ"), "usb")

    def test_parse_devices_output(self):
        sample_output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
0123456789ABCDEF       device usb:1-1 product:redfin model:Pixel_5 device:redfin transport_id:1
192.168.1.105:5555     device product:sunfish model:Pixel_4a device:sunfish transport_id:2
adb-serial-xyz._adb-tls-connect._tcp. device product:bar model:Foo_Bar device:bar transport_id:3
98899a444342345847     offline transport_id:4
unauth_serial          unauthorized usb:1-2 transport_id:5
noperm_serial          no permissions (missing udev rules?); see [http://...] usb:1-3 transport_id:6

"""
        devices = parse_devices_output(sample_output)
        self.assertEqual(len(devices), 6)

        # 1. USB normal device
        d1 = devices[0]
        self.assertEqual(d1.serial, "0123456789ABCDEF")
        self.assertEqual(d1.state, "device")
        self.assertEqual(d1.model, "Pixel_5")
        self.assertEqual(d1.display_model, "Pixel 5")
        self.assertEqual(d1.product, "redfin")
        self.assertEqual(d1.transport, "usb")
        self.assertEqual(d1.transport_display, "USB")
        self.assertEqual(d1.state_display, "Sẵn sàng")

        # 2. Wi-Fi device
        d2 = devices[1]
        self.assertEqual(d2.serial, "192.168.1.105:5555")
        self.assertEqual(d2.state, "device")
        self.assertEqual(d2.display_model, "Pixel 4a")
        self.assertEqual(d2.transport, "wifi")
        self.assertEqual(d2.transport_display, "Wi-Fi")

        # 3. TLS connect Wi-Fi
        d3 = devices[2]
        self.assertEqual(d3.transport, "wifi")
        self.assertEqual(d3.display_model, "Foo Bar")

        # 4. Offline
        d4 = devices[3]
        self.assertEqual(d4.serial, "98899a444342345847")
        self.assertEqual(d4.state, "offline")
        self.assertEqual(d4.state_display, "Offline")
        self.assertEqual(d4.display_model, "98899a444342345847")

        # 5. Unauthorized
        d5 = devices[4]
        self.assertEqual(d5.serial, "unauth_serial")
        self.assertEqual(d5.state, "unauthorized")
        self.assertEqual(d5.state_display, "Chưa cho phép (unauthorized)")

        # 6. No permissions
        d6 = devices[5]
        self.assertEqual(d6.serial, "noperm_serial")
        self.assertEqual(d6.state, "no permissions")

    def test_parse_devices_output_empty_or_daemon_only(self):
        output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached

"""
        devices = parse_devices_output(output)
        self.assertEqual(devices, [])

    def test_parse_ip_route(self):
        sample_route = """default via 192.168.1.1 dev wlan0 proto dhcp metric 100
192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.150
10.0.0.0/8 dev rmnet0 proto kernel scope link src 10.15.2.3
"""
        ip = parse_ip_route(sample_route)
        self.assertEqual(ip, "192.168.1.150")

        # No wlan interface
        cellular_only = "10.0.0.0/8 dev rmnet0 proto kernel scope link src 10.15.2.3\n"
        self.assertIsNone(parse_ip_route(cellular_only))

        # Empty
        self.assertIsNone(parse_ip_route(""))

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_list_devices(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "List of devices attached\n12345 device model:Test_Phone\n"
        mock_run.return_value = mock_proc

        devices = list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].serial, "12345")
        self.assertEqual(devices[0].display_model, "Test Phone")

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_connect_wifi_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "connected to 192.168.1.50:5555"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        ok, msg = connect_wifi("192.168.1.50:5555")
        self.assertTrue(ok)
        self.assertIn("connected to 192.168.1.50:5555", msg)

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_connect_wifi_failure(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "cannot connect to 192.168.1.50:5555: Connection refused"
        mock_run.return_value = mock_proc

        ok, msg = connect_wifi("192.168.1.50:5555")
        self.assertFalse(ok)
        self.assertIn("cannot connect", msg)

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_disconnect_wifi(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "disconnected 192.168.1.50:5555"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        ok, msg = disconnect_wifi("192.168.1.50:5555")
        self.assertTrue(ok)
        self.assertIn("disconnected", msg)

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_switch_to_wifi_flow(self, mock_run):
        # Step 1: ip route
        p1 = MagicMock(returncode=0, stdout="192.168.1.0/24 dev wlan0 src 192.168.1.80", stderr="")
        # Step 2: tcpip 5555
        p2 = MagicMock(returncode=0, stdout="restarting in TCP mode port: 5555", stderr="")
        # Step 3: connect
        p3 = MagicMock(returncode=0, stdout="connected to 192.168.1.80:5555", stderr="")
        mock_run.side_effect = [p1, p2, p3]

        ok, msg, ip = switch_to_wifi("usb_serial_123")
        self.assertTrue(ok)
        self.assertEqual(ip, "192.168.1.80")
        self.assertIn("192.168.1.80:5555", msg)

    @patch("scrcpy_gui.adb.run_adb_command")
    def test_switch_to_wifi_no_wlan_ip(self, mock_run):
        p1 = MagicMock(returncode=0, stdout="10.0.0.0/8 dev rmnet0 src 10.0.0.1", stderr="")
        mock_run.return_value = p1

        ok, msg, ip = switch_to_wifi("usb_serial_123")
        self.assertFalse(ok)
        self.assertIsNone(ip)
        self.assertIn("Không tìm thấy địa chỉ IP Wi-Fi", msg)


if __name__ == "__main__":
    unittest.main()
