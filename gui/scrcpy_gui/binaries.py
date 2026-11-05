"""Tìm đường dẫn thực thi của adb và scrcpy theo thứ tự ưu tiên."""

import os
import shutil
from typing import Optional


def find_binary(name: str, env_var: str) -> Optional[str]:
    """Tìm đường dẫn binary theo thứ tự ưu tiên:
    1. Biến môi trường (SCRCPY_BIN hoặc ADB)
    2. Thư mục cài đặt (thư mục cha của package khi đóng gói, vd. /opt/scrcpy-gui/scrcpy)
    3. Biến môi trường PATH
    Trả về đường dẫn tuyệt đối hoặc chuỗi lệnh, hoặc None nếu không tìm thấy.
    """
    # 1. Biến môi trường
    env_val = os.environ.get(env_var, "").strip()
    if env_val:
        if os.path.isfile(env_val) and os.access(env_val, os.X_OK):
            return os.path.abspath(env_val)
        which_env = shutil.which(env_val)
        if which_env:
            return which_env

    # 2. Thư mục cha của package khi đóng gói
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(pkg_dir)
    candidate = os.path.join(parent_dir, name)
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return os.path.abspath(candidate)
    if os.name == "nt":
        candidate_exe = os.path.join(parent_dir, f"{name}.exe")
        if os.path.isfile(candidate_exe) and os.access(candidate_exe, os.X_OK):
            return os.path.abspath(candidate_exe)

    # 3. PATH
    return shutil.which(name)


def find_scrcpy() -> Optional[str]:
    """Tìm binary scrcpy."""
    return find_binary("scrcpy", "SCRCPY_BIN")


def find_adb() -> Optional[str]:
    """Tìm binary adb."""
    return find_binary("adb", "ADB")
