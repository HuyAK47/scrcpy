"""Gọi lệnh adb và parse kết quả."""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .binaries import find_adb


@dataclass
class DeviceInfo:
    """Thông tin thiết bị adb."""
    serial: str
    state: str
    model: str = ""
    product: str = ""
    device: str = ""
    transport_id: str = ""
    transport: str = "usb"  # "usb" hoặc "wifi"

    @property
    def display_model(self) -> str:
        """Tên máy thay '_' bằng khoảng trắng; nếu không có tên thì hiển thị serial."""
        if self.model:
            return self.model.replace("_", " ")
        return self.serial

    @property
    def transport_display(self) -> str:
        """Chuỗi hiển thị loại kết nối."""
        return "Wi-Fi" if self.transport == "wifi" else "USB"

    @property
    def state_display(self) -> str:
        """Chuỗi hiển thị trạng thái tiếng Việt."""
        if self.state == "device":
            return "Sẵn sàng"
        if self.state == "unauthorized":
            return "Chưa cho phép (unauthorized)"
        if self.state == "offline":
            return "Offline"
        return self.state


def classify_transport(serial: str) -> str:
    """Xác định transport là 'wifi' hoặc 'usb'.

    transport = wifi nếu serial có dạng host:port (hoặc _adb-tls-connect._tcp),
    ngược lại là usb.
    """
    if "_adb-tls-connect._tcp" in serial:
        return "wifi"
    if re.search(r":\d+$", serial):
        return "wifi"
    return "usb"


def parse_devices_output(output: str) -> List[DeviceInfo]:
    """Parse kết quả từ lệnh `adb devices -l`."""
    devices: List[DeviceInfo] = []
    lines = output.strip().splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        # Bỏ qua thông báo khởi động daemon hoặc dòng tiêu đề
        if line.startswith("*") or line.startswith("List of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        # Xử lý trường hợp "no permissions"
        if len(parts) >= 3 and parts[1] == "no" and parts[2].startswith("permissions"):
            state = "no permissions"
            attrs = parts[3:]
        else:
            state = parts[1]
            attrs = parts[2:]

        info = {
            "model": "",
            "product": "",
            "device": "",
            "transport_id": "",
        }

        for attr in attrs:
            if ":" in attr:
                key, val = attr.split(":", 1)
                if key in info:
                    info[key] = val

        transport = classify_transport(serial)
        devices.append(
            DeviceInfo(
                serial=serial,
                state=state,
                model=info["model"],
                product=info["product"],
                device=info["device"],
                transport_id=info["transport_id"],
                transport=transport,
            )
        )

    return devices


def parse_ip_route(output: str) -> Optional[str]:
    """Parse địa chỉ IP của giao diện wlan từ kết quả `adb shell ip route`."""
    for line in output.splitlines():
        line = line.strip()
        if "wlan" in line:
            # Tìm src <ipv4>
            m = re.search(r"\bsrc\s+([0-9]{1,3}(?:\.[0-9]{1,3}){3})\b", line)
            if m:
                return m.group(1)
    return None


def run_adb_command(
    args: List[str],
    adb_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess:
    """Chạy lệnh adb đồng bộ với timeout."""
    bin_path = adb_bin or find_adb() or "adb"
    cmd = [bin_path] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def list_devices(
    adb_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> List[DeviceInfo]:
    """Lấy danh sách thiết bị adb."""
    try:
        proc = run_adb_command(["devices", "-l"], adb_bin=adb_bin, timeout=timeout)
        if proc.returncode == 0:
            return parse_devices_output(proc.stdout)
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def connect_wifi(
    ip_port: str,
    adb_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[bool, str]:
    """Kết nối thiết bị qua Wi-Fi bằng `adb connect <ip_port>`."""
    target = ip_port.strip()
    if not target:
        return False, "Địa chỉ IP:port không được để trống"

    if ":" not in target:
        target = f"{target}:5555"

    try:
        proc = run_adb_command(["connect", target], adb_bin=adb_bin, timeout=timeout)
        output = (proc.stdout + "\n" + proc.stderr).strip()
        out_lower = output.lower()
        if "connected to" in out_lower or "already connected to" in out_lower:
            return True, output
        return False, output or "Kết nối thất bại"
    except subprocess.TimeoutExpired:
        return False, f"Quá thời gian ({timeout}s) khi kết nối tới {target}"
    except (FileNotFoundError, OSError) as e:
        return False, f"Lỗi thực thi adb: {e}"


def disconnect_wifi(
    serial: str,
    adb_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[bool, str]:
    """Ngắt kết nối thiết bị Wi-Fi bằng `adb disconnect <serial>`."""
    target = serial.strip()
    if not target:
        return False, "Serial không được để trống"

    try:
        proc = run_adb_command(["disconnect", target], adb_bin=adb_bin, timeout=timeout)
        output = (proc.stdout + "\n" + proc.stderr).strip()
        if proc.returncode == 0:
            return True, output or f"Đã ngắt kết nối {target}"
        return False, output or f"Ngắt kết nối {target} thất bại"
    except subprocess.TimeoutExpired:
        return False, f"Quá thời gian ({timeout}s) khi ngắt kết nối {target}"
    except (FileNotFoundError, OSError) as e:
        return False, f"Lỗi thực thi adb: {e}"


def switch_to_wifi(
    serial: str,
    adb_bin: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[bool, str, Optional[str]]:
    """Chuyển thiết bị USB sang Wi-Fi:
    1. Lấy IP qua `adb -s <serial> shell ip route`
    2. Chạy `adb -s <serial> tcpip 5555`
    3. Chạy `adb connect <ip>:5555`
    """
    target = serial.strip()
    if not target:
        return False, "Serial không được để trống", None

    try:
        # Bước 1: Lấy IP
        ip_proc = run_adb_command(
            ["-s", target, "shell", "ip", "route"],
            adb_bin=adb_bin,
            timeout=timeout,
        )
        if ip_proc.returncode != 0:
            err = (ip_proc.stderr or ip_proc.stdout).strip()
            return False, f"Không thể lấy route mạng từ thiết bị ({err})", None

        ip = parse_ip_route(ip_proc.stdout)
        if not ip:
            return (
                False,
                "Không tìm thấy địa chỉ IP Wi-Fi (giao diện wlan). Hãy chắc chắn điện thoại đã kết nối mạng Wi-Fi.",
                None,
            )

        # Bước 2: Chuyển sang tcpip 5555
        tcpip_proc = run_adb_command(
            ["-s", target, "tcpip", "5555"],
            adb_bin=adb_bin,
            timeout=timeout,
        )
        if tcpip_proc.returncode != 0:
            err = (tcpip_proc.stderr or tcpip_proc.stdout).strip()
            return False, f"Lỗi khi chuyển adb sang tcpip 5555: {err}", ip

        # Bước 3: Kết nối Wi-Fi
        connect_proc = run_adb_command(
            ["connect", f"{ip}:5555"],
            adb_bin=adb_bin,
            timeout=timeout,
        )
        connect_out = (connect_proc.stdout + "\n" + connect_proc.stderr).strip()
        out_lower = connect_out.lower()
        if "connected to" in out_lower or "already connected to" in out_lower:
            return True, f"Kết nối Wi-Fi thành công: {ip}:5555", ip

        return False, f"Đã bật tcpip 5555 nhưng kết nối tới {ip}:5555 thất bại: {connect_out}", ip

    except subprocess.TimeoutExpired:
        return False, f"Quá thời gian ({timeout}s) khi chuyển thiết bị sang Wi-Fi", None
    except (FileNotFoundError, OSError) as e:
        return False, f"Lỗi thực thi adb: {e}", None
