"""Unit tests for scrcpy command builder and process launcher."""

import os
import subprocess
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Add gui directory to sys.path
_gui_dir = str(Path(__file__).resolve().parent.parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from scrcpy_gui.launcher import Launcher, build_scrcpy_command
from scrcpy_gui.settings import Settings


class TestLauncher(unittest.TestCase):
    def test_build_scrcpy_command_defaults(self):
        cmd = build_scrcpy_command(
            serial="0123456789ABCDEF",
            model="Pixel_4",
            scrcpy_bin="/usr/bin/scrcpy",
        )
        self.assertEqual(cmd[0], "/usr/bin/scrcpy")
        self.assertEqual(cmd[1], "-s")
        self.assertEqual(cmd[2], "0123456789ABCDEF")
        self.assertIn("--window-title", cmd)
        title_idx = cmd.index("--window-title")
        self.assertEqual(cmd[title_idx + 1], "Pixel 4 (0123456789ABCDEF)")
        self.assertIn("--video-bit-rate", cmd)
        br_idx = cmd.index("--video-bit-rate")
        self.assertEqual(cmd[br_idx + 1], "8M")
        # Ensure default "Không giới hạn" does not add --max-size or --max-fps
        self.assertNotIn("--max-size", cmd)
        self.assertNotIn("--max-fps", cmd)
        self.assertNotIn("--no-audio", cmd)

    def test_build_scrcpy_command_all_options(self):
        cfg = Settings(
            max_size="1920",
            bitrate="16M",
            max_fps="60",
            no_audio=True,
            turn_screen_off=True,
            stay_awake=True,
            always_on_top=True,
            fullscreen=True,
            extra_args="--record=demo.mp4 --shortcut-mod=lalt",
        )
        cmd = build_scrcpy_command(
            serial="192.168.1.50:5555",
            model="Galaxy_S21",
            settings=cfg,
            scrcpy_bin="scrcpy",
        )
        self.assertIn("--max-size", cmd)
        self.assertEqual(cmd[cmd.index("--max-size") + 1], "1920")

        self.assertIn("--video-bit-rate", cmd)
        self.assertEqual(cmd[cmd.index("--video-bit-rate") + 1], "16M")

        self.assertIn("--max-fps", cmd)
        self.assertEqual(cmd[cmd.index("--max-fps") + 1], "60")

        self.assertIn("--no-audio", cmd)
        self.assertIn("--turn-screen-off", cmd)
        self.assertIn("--stay-awake", cmd)
        self.assertIn("--always-on-top", cmd)
        self.assertIn("--fullscreen", cmd)

        self.assertIn("--record=demo.mp4", cmd)
        self.assertIn("--shortcut-mod=lalt", cmd)

    def test_build_scrcpy_command_empty_model(self):
        cmd = build_scrcpy_command(serial="XYZ123", model="", scrcpy_bin="scrcpy")
        title_idx = cmd.index("--window-title")
        self.assertEqual(cmd[title_idx + 1], "XYZ123 (XYZ123)")

    @patch.dict(os.environ, {"SCRCPY_SERVER_PATH": "/opt/scrcpy/scrcpy-server"}, clear=True)
    @patch("subprocess.Popen")
    def test_launcher_passes_scrcpy_server_path(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc

        launcher = Launcher(scrcpy_bin="scrcpy")
        launcher.start(serial="serial_1")

        self.assertTrue(mock_popen.called)
        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs.get("env", {})
        self.assertEqual(env.get("SCRCPY_SERVER_PATH"), "/opt/scrcpy/scrcpy-server")

    @patch("subprocess.Popen")
    def test_launcher_lifecycle_and_exit_detection(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter(["ERROR: Device disconnected\n", "scrcpy finished with error\n"])
        mock_popen.return_value = mock_proc

        launcher = Launcher(scrcpy_bin="scrcpy")
        session = launcher.start(serial="dev1", model="TestPhone")

        self.assertTrue(launcher.is_running("dev1"))
        self.assertTrue(launcher.has_active_sessions())
        self.assertEqual(launcher.get_running_serials(), ["dev1"])

        # No exited process yet
        exited = launcher.check_exited()
        self.assertEqual(exited, [])

        # Simulate process exiting with error code 1
        mock_proc.poll.return_value = 1
        exited = launcher.check_exited()
        self.assertEqual(len(exited), 1)
        serial, code, stderr_msg = exited[0]
        self.assertEqual(serial, "dev1")
        self.assertEqual(code, 1)
        self.assertIn("Device disconnected", stderr_msg)

        # After detection, session is cleaned up
        self.assertFalse(launcher.is_running("dev1"))
        self.assertFalse(launcher.has_active_sessions())

    @patch("subprocess.Popen")
    def test_launcher_stop(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc

        launcher = Launcher(scrcpy_bin="scrcpy")
        launcher.start(serial="dev_to_stop")
        self.assertTrue(launcher.is_running("dev_to_stop"))

        launcher.stop("dev_to_stop")
        mock_proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
