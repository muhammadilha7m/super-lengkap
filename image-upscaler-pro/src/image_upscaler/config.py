"""Persistent user configuration.

Settings are stored in a JSON file under the per-user app data directory:

* Windows: ``%APPDATA%\\ImageUpscalerPro\\config.json``
* macOS:   ``~/Library/Application Support/ImageUpscalerPro/config.json``
* Linux:   ``~/.config/ImageUpscalerPro/config.json``
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    APP_SHORT_NAME,
    DEFAULT_CONFLICT_MODE,
    DEFAULT_ENGINE,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_REALESRGAN_MODEL,
    DEFAULT_SCALE,
    DEFAULT_WEBP_QUALITY,
)

log = logging.getLogger(__name__)


def app_data_dir() -> Path:
    """Return the per-user directory where application data is stored."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_SHORT_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_SHORT_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / APP_SHORT_NAME


def config_path() -> Path:
    return app_data_dir() / "config.json"


@dataclass
class AppConfig:
    """User-tunable settings."""

    engine: str = DEFAULT_ENGINE
    realesrgan_model: str = DEFAULT_REALESRGAN_MODEL
    scale: int = DEFAULT_SCALE
    output_format: str = DEFAULT_OUTPUT_FORMAT
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    webp_quality: int = DEFAULT_WEBP_QUALITY
    output_dir: str = ""  # empty = next to source file
    conflict_mode: str = DEFAULT_CONFLICT_MODE
    appearance_mode: str = "dark"  # "dark" | "light" | "white" | "system"
    accent_color: str = "blue"  # "blue" | "purple" | "green"
    preserve_exif: bool = True
    play_sound_on_done: bool = True
    show_desktop_notification: bool = True
    recursive_folder_scan: bool = True
    realesrgan_binary: str = ""  # explicit path to realesrgan-ncnn-vulkan(.exe)
    recent_input_dirs: list[str] = field(default_factory=list)
    recent_output_dirs: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> AppConfig:
        path = config_path()
        if not path.exists():
            return cls()
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Failed to load config from %s: %s", path, exc)
            return cls()
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**clean)
        except TypeError as exc:
            log.warning("Config has incompatible schema, using defaults: %s", exc)
            return cls()

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def remember_input_dir(self, directory: str) -> None:
        self._remember(self.recent_input_dirs, directory)

    def remember_output_dir(self, directory: str) -> None:
        self._remember(self.recent_output_dirs, directory)

    @staticmethod
    def _remember(bucket: list[str], directory: str, limit: int = 8) -> None:
        if not directory:
            return
        if directory in bucket:
            bucket.remove(directory)
        bucket.insert(0, directory)
        del bucket[limit:]
