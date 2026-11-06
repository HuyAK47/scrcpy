"""Quản lý tuỳ chọn cấu hình ứng dụng."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Danh sách lựa chọn hiển thị trên UI
MAX_SIZE_OPTIONS = ["Không giới hạn", "1920", "1280", "1024", "800"]
BITRATE_OPTIONS = ["4M", "8M", "16M"]
MAX_FPS_OPTIONS = ["Không giới hạn", "30", "60"]
PREVIEW_INTERVAL_OPTIONS = ["2s", "5s", "10s"]


@dataclass
class Settings:
    """Các tuỳ chọn cấu hình scrcpy."""
    max_size: str = "Không giới hạn"
    bitrate: str = "8M"
    max_fps: str = "Không giới hạn"
    no_audio: bool = False
    turn_screen_off: bool = False
    stay_awake: bool = False
    always_on_top: bool = False
    fullscreen: bool = False
    extra_args: str = ""
    preview_enabled: bool = False
    preview_interval: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "Settings":
        if not isinstance(data, dict):
            return cls()

        default = cls()

        raw_interval = data.get("preview_interval", default.preview_interval)
        if isinstance(raw_interval, str):
            clean_int = raw_interval.rstrip("sS ").strip()
            try:
                interval_val = int(clean_int)
            except ValueError:
                interval_val = default.preview_interval
        elif isinstance(raw_interval, (int, float)):
            interval_val = int(raw_interval)
        else:
            interval_val = default.preview_interval

        if interval_val not in (2, 5, 10):
            interval_val = default.preview_interval

        return cls(
            max_size=str(data.get("max_size", default.max_size)),
            bitrate=str(data.get("bitrate", default.bitrate)),
            max_fps=str(data.get("max_fps", default.max_fps)),
            no_audio=bool(data.get("no_audio", default.no_audio)),
            turn_screen_off=bool(data.get("turn_screen_off", default.turn_screen_off)),
            stay_awake=bool(data.get("stay_awake", default.stay_awake)),
            always_on_top=bool(data.get("always_on_top", default.always_on_top)),
            fullscreen=bool(data.get("fullscreen", default.fullscreen)),
            extra_args=str(data.get("extra_args", default.extra_args)),
            preview_enabled=bool(data.get("preview_enabled", default.preview_enabled)),
            preview_interval=interval_val,
        )


def get_config_path() -> Path:
    """Lấy đường dẫn tệp settings.json tôn trọng XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        base_dir = Path(xdg)
    else:
        base_dir = Path.home() / ".config"
    return base_dir / "scrcpy-gui" / "settings.json"


def load_settings(path: Optional[Path] = None) -> Settings:
    """Đọc cài đặt từ tệp JSON.

    Nếu tệp không tồn tại hoặc bị hỏng, trả về cài đặt mặc định không crash.
    """
    cfg_file = path or get_config_path()
    if not cfg_file.is_file():
        return Settings()

    try:
        content = cfg_file.read_text(encoding="utf-8")
        data = json.loads(content)
        return Settings.from_dict(data)
    except Exception:
        # File hỏng hoặc không đọc được -> dùng mặc định
        return Settings()


def save_settings(settings: Settings, path: Optional[Path] = None) -> bool:
    """Lưu cài đặt vào tệp JSON."""
    cfg_file = path or get_config_path()
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
        cfg_file.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False
