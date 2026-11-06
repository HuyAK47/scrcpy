"""Xử lý chụp màn hình, tính toán ảnh thu nhỏ và chế độ xếp lưới live."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import math
import os
import struct
import subprocess
import threading
from typing import Callable, Dict, List, Optional, Set, Tuple

from .binaries import find_adb, find_scrcpy

DEFAULT_CAPTURE_TIMEOUT: float = 8.0


class PreviewCaptureError(Exception):
    """Lỗi phát sinh trong quá trình chụp hoặc xử lý ảnh preview."""


def parse_png_dimensions(data: bytes) -> Tuple[int, int]:
    """Phân tích kích thước (width, height) từ dữ liệu nhị phân PNG.

    Đọc thông số từ khối IHDR theo chuẩn PNG mà không cần phụ thuộc thư viện ngoài.
    Ném PreviewCaptureError nếu dữ liệu không phải PNG hợp lệ.
    """
    if len(data) < 24:
        raise PreviewCaptureError("Dữ liệu ảnh quá ngắn để đọc kích thước PNG")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PreviewCaptureError("Header không khớp định dạng PNG")
    if data[12:16] != b"IHDR":
        raise PreviewCaptureError("Không tìm thấy khối IHDR trong PNG")

    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise PreviewCaptureError(f"Kích thước PNG không hợp lệ: {width}x{height}")
    return width, height


def compute_subsample_factor(orig_w: int, orig_h: int, target_w: int, target_h: int) -> int:
    """Tính hệ số thu nhỏ nguyên (subsample factor >= 1) cho tk.PhotoImage.

    Hệ số n sao cho kích thước sau thu nhỏ (orig_w // n, orig_h // n)
    vừa vặn trong khung mục tiêu (target_w, target_h).
    """
    if orig_w <= 0 or orig_h <= 0 or target_w <= 0 or target_h <= 0:
        return 1

    if orig_w <= target_w and orig_h <= target_h:
        return 1

    factor_w = orig_w / target_w
    factor_h = orig_h / target_h
    factor = math.ceil(max(factor_w, factor_h))
    return max(1, factor)


def capture_screenshot(
    serial: str,
    adb_bin: Optional[str] = None,
    timeout: float = DEFAULT_CAPTURE_TIMEOUT,
) -> bytes:
    """Chụp màn hình thiết bị Android qua lệnh 'adb exec-out screencap -p'.

    Trả về chuỗi bytes dữ liệu PNG. Ném PreviewCaptureError nếu lỗi hoặc timeout.
    """
    bin_path = adb_bin or find_adb() or "adb"
    cmd = [bin_path, "-s", serial, "exec-out", "screencap", "-p"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        raise PreviewCaptureError(f"Không thể khởi chạy adb: {e}") from e

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        try:
            proc.kill()
            proc.communicate()
        except Exception:
            pass
        raise PreviewCaptureError(f"Hết thời gian chụp màn hình ({timeout}s)") from e
    except Exception as e:
        try:
            proc.kill()
            proc.communicate()
        except Exception:
            pass
        raise PreviewCaptureError(f"Lỗi chụp màn hình: {e}") from e

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace").strip() if stderr else f"Mã lỗi {proc.returncode}"
        raise PreviewCaptureError(f"Lệnh screencap thất bại: {err_msg}")

    if not stdout or not stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        snippet = stdout[:60].decode("utf-8", errors="replace").strip() if stdout else "Không có dữ liệu"
        raise PreviewCaptureError(f"Dữ liệu ảnh không hợp lệ: {snippet}")

    return stdout


def compute_tile_geometry(
    index: int,
    total: int,
    screen_w: int,
    screen_h: int,
) -> Tuple[int, int, int, int]:
    """Tính toạ độ (x, y, width, height) để xếp các cửa sổ live dạng bàn cờ trên màn hình."""
    if total <= 1:
        return (0, 0, screen_w, screen_h)

    cols = math.ceil(math.sqrt(total))
    rows = math.ceil(total / cols)

    tile_w = max(1, screen_w // cols)
    tile_h = max(1, screen_h // rows)

    col = index % cols
    row = index // cols

    x = col * tile_w
    y = row * tile_h
    return (x, y, tile_w, tile_h)


def build_live_command(
    serial: str,
    model: str = "",
    geometry: Optional[Tuple[int, int, int, int]] = None,
    scrcpy_bin: Optional[str] = None,
) -> List[str]:
    """Dựng danh sách đối số cho lệnh scrcpy ở chế độ xem trước trực tiếp (Live Tiling)."""
    bin_path = scrcpy_bin or find_scrcpy() or "scrcpy"
    clean_model = model.replace("_", " ").strip() if model else serial
    title = f"{clean_model} ({serial}) [live]"

    cmd: List[str] = [
        bin_path,
        "-s",
        serial,
        "--window-title",
        title,
        "--no-control",
        "--no-audio",
        "--window-borderless",
        "--max-size",
        "360",
        "--max-fps",
        "10",
        "--video-bit-rate",
        "1M",
    ]

    if geometry:
        x, y, w, h = geometry
        cmd.extend([
            "--window-x",
            str(x),
            "--window-y",
            str(y),
            "--window-width",
            str(w),
            "--window-height",
            str(h),
        ])

    return cmd


class PreviewManager:
    """Quản lý các tác vụ chụp màn hình preview định kỳ và song song."""

    def __init__(
        self,
        adb_bin: Optional[str] = None,
        max_workers: int = 4,
        timeout: float = DEFAULT_CAPTURE_TIMEOUT,
    ):
        self.adb_bin = adb_bin
        self.timeout = timeout
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._enabled = False
        self._active_serials: Set[str] = set()
        self._active_procs: Dict[str, subprocess.Popen] = {}
        self._executor: Optional[ThreadPoolExecutor] = None

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
            if not enabled:
                self._cancel_all_locked()

    def is_capturing(self, serial: str) -> bool:
        """Kiểm tra xem thiết bị có đang trong tiến trình chụp hay không."""
        with self._lock:
            return serial in self._active_serials

    def start_capture(
        self,
        serial: str,
        on_success: Callable[[str, bytes], None],
        on_error: Callable[[str, str], None],
    ) -> bool:
        """Yêu cầu chụp màn hình cho 1 thiết bị.

        Trả về True nếu tác vụ được lập lịch, False nếu preview tắt hoặc đang có lệnh chụp chạy cho serial này.
        """
        with self._lock:
            if not self._enabled:
                return False
            if serial in self._active_serials:
                return False
            self._active_serials.add(serial)
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
            executor = self._executor

        def worker():
            try:
                data = self._execute_capture(serial)
                with self._lock:
                    if not self._enabled:
                        return
                on_success(serial, data)
            except PreviewCaptureError as e:
                with self._lock:
                    if not self._enabled:
                        return
                on_error(serial, str(e))
            except Exception as e:
                with self._lock:
                    if not self._enabled:
                        return
                on_error(serial, f"Lỗi không xác định: {e}")
            finally:
                with self._lock:
                    self._active_serials.discard(serial)

        executor.submit(worker)
        return True

    def _execute_capture(self, serial: str) -> bytes:
        bin_path = self.adb_bin or find_adb() or "adb"
        cmd = [bin_path, "-s", serial, "exec-out", "screencap", "-p"]

        with self._lock:
            if not self._enabled:
                raise PreviewCaptureError("Preview đã bị tắt")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as e:
            raise PreviewCaptureError(f"Không thể khởi chạy adb: {e}") from e

        with self._lock:
            if not self._enabled:
                proc.kill()
                proc.communicate()
                raise PreviewCaptureError("Preview đã bị tắt")
            self._active_procs[serial] = proc

        try:
            stdout, stderr = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
            raise PreviewCaptureError(f"Hết thời gian chụp màn hình ({self.timeout}s)") from e
        except Exception as e:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
            raise PreviewCaptureError(f"Lỗi chụp màn hình: {e}") from e
        finally:
            with self._lock:
                self._active_procs.pop(serial, None)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip() if stderr else f"Mã lỗi {proc.returncode}"
            raise PreviewCaptureError(f"Chụp thất bại: {err_msg}")

        if not stdout or not stdout.startswith(b"\x89PNG\r\n\x1a\n"):
            snippet = stdout[:60].decode("utf-8", errors="replace").strip() if stdout else "Không có dữ liệu"
            raise PreviewCaptureError(f"Dữ liệu ảnh không hợp lệ: {snippet}")

        return stdout

    def cancel_all(self) -> None:
        """Dừng tất cả các lệnh chụp đang chạy."""
        with self._lock:
            self._cancel_all_locked()

    def _cancel_all_locked(self) -> None:
        for proc in list(self._active_procs.values()):
            try:
                proc.kill()
            except OSError:
                pass
        self._active_procs.clear()
        self._active_serials.clear()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
