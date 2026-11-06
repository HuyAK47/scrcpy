"""Unit tests for settings management."""

import json
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

# Add gui directory to sys.path
_gui_dir = str(Path(__file__).resolve().parent.parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from scrcpy_gui.settings import Settings, get_config_path, load_settings, save_settings


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_settings(self):
        s = Settings()
        self.assertEqual(s.max_size, "Không giới hạn")
        self.assertEqual(s.bitrate, "8M")
        self.assertEqual(s.max_fps, "Không giới hạn")
        self.assertFalse(s.no_audio)
        self.assertFalse(s.turn_screen_off)
        self.assertFalse(s.stay_awake)
        self.assertFalse(s.always_on_top)
        self.assertFalse(s.fullscreen)
        self.assertEqual(s.extra_args, "")
        self.assertFalse(s.preview_enabled)
        self.assertEqual(s.preview_interval, 2)

    def test_save_and_load(self):
        cfg_file = self.temp_path / "settings.json"
        s = Settings(
            max_size="1920",
            bitrate="16M",
            max_fps="60",
            no_audio=True,
            turn_screen_off=True,
            stay_awake=True,
            always_on_top=True,
            fullscreen=True,
            extra_args="--record=demo.mp4",
            preview_enabled=True,
            preview_interval=5,
        )
        self.assertTrue(save_settings(s, cfg_file))
        self.assertTrue(cfg_file.is_file())

        loaded = load_settings(cfg_file)
        self.assertEqual(loaded.max_size, "1920")
        self.assertEqual(loaded.bitrate, "16M")
        self.assertEqual(loaded.max_fps, "60")
        self.assertTrue(loaded.no_audio)
        self.assertTrue(loaded.turn_screen_off)
        self.assertTrue(loaded.stay_awake)
        self.assertTrue(loaded.always_on_top)
        self.assertTrue(loaded.fullscreen)
        self.assertEqual(loaded.extra_args, "--record=demo.mp4")
        self.assertTrue(loaded.preview_enabled)
        self.assertEqual(loaded.preview_interval, 5)

    def test_from_dict_variations(self):
        # Default when empty
        s_empty = Settings.from_dict({})
        self.assertFalse(s_empty.preview_enabled)
        self.assertEqual(s_empty.preview_interval, 2)

        # String format interval e.g. "5s", "10s"
        s_str5 = Settings.from_dict({"preview_enabled": True, "preview_interval": "5s"})
        self.assertTrue(s_str5.preview_enabled)
        self.assertEqual(s_str5.preview_interval, 5)

        s_str10 = Settings.from_dict({"preview_interval": "10s"})
        self.assertEqual(s_str10.preview_interval, 10)

        # Invalid interval falls back to default
        s_invalid = Settings.from_dict({"preview_interval": "abc"})
        self.assertEqual(s_invalid.preview_interval, 2)

    def test_load_corrupted_json(self):
        cfg_file = self.temp_path / "corrupted.json"
        cfg_file.write_text("{invalid json format: missing quotes", encoding="utf-8")

        # Must not crash, should return defaults
        loaded = load_settings(cfg_file)
        self.assertEqual(loaded.bitrate, "8M")
        self.assertEqual(loaded.max_size, "Không giới hạn")

    def test_load_non_dict_json(self):
        cfg_file = self.temp_path / "nondict.json"
        cfg_file.write_text("[1, 2, 3]", encoding="utf-8")

        loaded = load_settings(cfg_file)
        self.assertEqual(loaded.bitrate, "8M")

    def test_load_non_existent(self):
        cfg_file = self.temp_path / "does_not_exist.json"
        loaded = load_settings(cfg_file)
        self.assertEqual(loaded.bitrate, "8M")

    def test_xdg_config_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.temp_path)}, clear=True):
            p = get_config_path()
            self.assertEqual(p, self.temp_path / "scrcpy-gui" / "settings.json")


if __name__ == "__main__":
    unittest.main()
