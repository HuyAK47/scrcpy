"""Unit tests for binary discovery."""

import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

# Add gui directory to sys.path
_gui_dir = str(Path(__file__).resolve().parent.parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from scrcpy_gui.binaries import find_adb, find_binary, find_scrcpy


class TestBinaries(unittest.TestCase):
    @patch.dict(os.environ, {"ADB": "/custom/bin/adb"}, clear=True)
    @patch("os.path.isfile")
    @patch("os.access")
    def test_find_adb_from_env(self, mock_access, mock_isfile):
        mock_isfile.return_value = True
        mock_access.return_value = True
        self.assertEqual(find_adb(), os.path.abspath("/custom/bin/adb"))

    @patch.dict(os.environ, {"SCRCPY_BIN": "/custom/bin/scrcpy"}, clear=True)
    @patch("os.path.isfile")
    @patch("os.access")
    def test_find_scrcpy_from_env(self, mock_access, mock_isfile):
        mock_isfile.return_value = True
        mock_access.return_value = True
        self.assertEqual(find_scrcpy(), os.path.abspath("/custom/bin/scrcpy"))

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.isfile")
    @patch("os.access")
    @patch("shutil.which")
    def test_find_binary_package_parent_priority(self, mock_which, mock_access, mock_isfile):
        # Env var is empty.
        # Package parent has the file.
        mock_isfile.return_value = True
        mock_access.return_value = True
        mock_which.return_value = "/usr/bin/scrcpy"

        result = find_scrcpy()
        self.assertIsNotNone(result)
        # Should NOT be /usr/bin/scrcpy because package parent comes before PATH
        self.assertNotEqual(result, "/usr/bin/scrcpy")
        self.assertTrue(result.endswith("scrcpy"))

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which")
    def test_find_binary_from_path(self, mock_which, mock_isfile):
        mock_which.return_value = "/usr/bin/adb"
        self.assertEqual(find_adb(), "/usr/bin/adb")
        mock_which.assert_called_with("adb")

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value=None)
    def test_find_binary_not_found(self, mock_which, mock_isfile):
        self.assertIsNone(find_adb())
        self.assertIsNone(find_scrcpy())


if __name__ == "__main__":
    unittest.main()
