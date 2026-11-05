"""Dựng lệnh scrcpy và quản lý tiến trình."""

import collections
import os
import shlex
import subprocess
import threading
from typing import Deque, Dict, List, Optional, Tuple

from .binaries import find_scrcpy
from .settings import Settings


def build_scrcpy_command(
    serial: str,
    model: str = "",
    settings: Optional[Settings] = None,
    scrcpy_bin: Optional[str] = None,
) -> List[str]:
    """Dựng danh sách đối số cho lệnh scrcpy."""
    bin_path = scrcpy_bin or find_scrcpy() or "scrcpy"
    cfg = settings or Settings()

    cmd: List[str] = [bin_path, "-s", serial]

    # Tiêu đề cửa sổ: "<model> (<serial>)"
    clean_model = model.replace("_", " ").strip() if model else serial
    title = f"{clean_model} ({serial})"
    cmd.extend(["--window-title", title])

    # Độ phân giải tối đa
    if cfg.max_size and cfg.max_size != "Không giới hạn":
        cmd.extend(["--max-size", str(cfg.max_size)])

    # Video bitrate
    if cfg.bitrate:
        cmd.extend(["--video-bit-rate", str(cfg.bitrate)])

    # FPS tối đa
    if cfg.max_fps and cfg.max_fps != "Không giới hạn":
        cmd.extend(["--max-fps", str(cfg.max_fps)])

    # Các cờ tuỳ chọn boolean
    if cfg.no_audio:
        cmd.append("--no-audio")
    if cfg.turn_screen_off:
        cmd.append("--turn-screen-off")
    if cfg.stay_awake:
        cmd.append("--stay-awake")
    if cfg.always_on_top:
        cmd.append("--always-on-top")
    if cfg.fullscreen:
        cmd.append("--fullscreen")

    # Tham số bổ sung (tách bằng shlex.split)
    if cfg.extra_args and cfg.extra_args.strip():
        try:
            extra_tokens = shlex.split(cfg.extra_args.strip())
            cmd.extend(extra_tokens)
        except ValueError:
            # Nếu cú pháp shlex lỗi thì split thường
            cmd.extend(cfg.extra_args.strip().split())

    return cmd


class ScrcpySession:
    """Phiên chạy của một tiến trình scrcpy."""

    def __init__(self, serial: str, process: subprocess.Popen, cmd: List[str]):
        self.serial = serial
        self.process = process
        self.cmd = cmd
        self.stderr_lines: Deque[str] = collections.deque(maxlen=20)
        self._reader_thread = threading.Thread(
            target=self._read_stderr,
            name=f"scrcpy-stderr-{serial}",
            daemon=True,
        )
        self._reader_thread.start()

    def _read_stderr(self) -> None:
        if not self.process.stderr:
            return
        try:
            for line in self.process.stderr:
                self.stderr_lines.append(line)
        except Exception:
            pass

    def is_running(self) -> bool:
        return self.process.poll() is None

    def poll(self) -> Optional[int]:
        return self.process.poll()

    def stop(self) -> None:
        if self.is_running():
            try:
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self.process.kill()
                except OSError:
                    pass

    def get_last_stderr(self) -> str:
        return "".join(self.stderr_lines).strip()


class Launcher:
    """Quản lý các tiến trình scrcpy."""

    def __init__(self, scrcpy_bin: Optional[str] = None):
        self.scrcpy_bin = scrcpy_bin
        self.sessions: Dict[str, ScrcpySession] = {}
        self._lock = threading.Lock()

    def is_running(self, serial: str) -> bool:
        with self._lock:
            session = self.sessions.get(serial)
            if not session:
                return False
            return session.is_running()

    def start(
        self,
        serial: str,
        model: str = "",
        settings: Optional[Settings] = None,
    ) -> ScrcpySession:
        """Khởi chạy scrcpy cho thiết bị serial."""
        with self._lock:
            if serial in self.sessions and self.sessions[serial].is_running():
                return self.sessions[serial]

            cmd = build_scrcpy_command(
                serial=serial,
                model=model,
                settings=settings,
                scrcpy_bin=self.scrcpy_bin,
            )

            # Đảm bảo giữ nguyên biến môi trường SCRCPY_SERVER_PATH nếu có
            env = os.environ.copy()
            if "SCRCPY_SERVER_PATH" in os.environ:
                env["SCRCPY_SERVER_PATH"] = os.environ["SCRCPY_SERVER_PATH"]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            session = ScrcpySession(serial=serial, process=proc, cmd=cmd)
            self.sessions[serial] = session
            return session

    def stop(self, serial: str) -> bool:
        """Dừng tiến trình scrcpy cho thiết bị."""
        with self._lock:
            session = self.sessions.get(serial)
            if session:
                session.stop()
                return True
            return False

    def stop_all(self) -> None:
        """Dừng tất cả các tiến trình scrcpy đang chạy."""
        with self._lock:
            for session in list(self.sessions.values()):
                session.stop()

    def check_exited(self) -> List[Tuple[str, int, str]]:
        """Kiểm tra và trả về danh sách các tiến trình vừa mới kết thúc.

        Mỗi phần tử: (serial, returncode, last_stderr)
        Đồng thời dọn dẹp các session đã kết thúc khỏi active tracker.
        """
        exited = []
        with self._lock:
            for serial, session in list(self.sessions.items()):
                code = session.poll()
                if code is not None:
                    # Chờ thread đọc stderr nạp xong
                    session._reader_thread.join(timeout=0.2)
                    stderr_msg = session.get_last_stderr()
                    exited.append((serial, code, stderr_msg))
                    del self.sessions[serial]
        return exited

    def has_active_sessions(self) -> bool:
        """Có bất kỳ cửa sổ scrcpy nào đang mở không."""
        with self._lock:
            return any(s.is_running() for s in self.sessions.values())

    def get_running_serials(self) -> List[str]:
        """Danh sách serial đang chạy."""
        with self._lock:
            return [serial for serial, s in self.sessions.items() if s.is_running()]
