import sys
from pathlib import Path

# Đảm bảo package scrcpy_gui nằm trong sys.path khi chạy test
gui_dir = str(Path(__file__).resolve().parent.parent)
if gui_dir not in sys.path:
    sys.path.insert(0, gui_dir)
