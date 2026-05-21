"""Config loader & writer with sensible defaults.

The app reads ``config/settings.json`` at startup. Keys can be overridden via
environment variables, e.g. ``GROQ_API_KEY`` always takes precedence over the
``ai.api_key`` field.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "settings.json"
LOCAL_CONFIG_PATH = ROOT / "config" / "settings.local.json"


DEFAULTS: dict[str, Any] = {
    "app": {"name": "Spectrum AI", "version": "0.1.0", "theme": "dark-glass", "language": "id"},
    "ai": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "models_available": [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "mixtral-8x7b-32768",
        ],
        "api_key": "",
        "api_key_env": "GROQ_API_KEY",
        "temperature": 0.8,
        "max_tokens": 1024,
    },
    "render": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "codec": "libx264",
        "crf": 18,
        "preset": "medium",
        "audio_bitrate": "192k",
        "gpu": "auto",
    },
    "performance": {"mode": "balanced"},
    "paths": {
        "projects": "projects",
        "exports": "exports",
        "cache": "cache",
        "logs": "logs",
        "assets": "assets",
    },
    "audio": {
        "sample_rate": 44100,
        "fft_size": 2048,
        "hop_length": 512,
        "n_mels": 128,
        "spectrum_bands": 64,
    },
    "ui": {"frameless": True, "preview_fps": 30, "preview_scale": 0.5},
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    """Mutable, dot-access friendly config container."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = _deep_merge(DEFAULTS, data or {})

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        cfg = cls()
        for candidate in (path or CONFIG_PATH, LOCAL_CONFIG_PATH):
            if candidate and candidate.exists():
                try:
                    cfg._data = _deep_merge(cfg._data, json.loads(candidate.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        cfg._apply_env()
        return cfg

    def _apply_env(self) -> None:
        env_key = self._data.get("ai", {}).get("api_key_env", "GROQ_API_KEY")
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            self._data["ai"]["api_key"] = env_val

    def save(self, path: Path | None = None) -> None:
        target = path or CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ----- dict-like helpers ---------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self._data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        cur = self._data
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    # ----- path helpers --------------------------------------------------
    def path(self, name: str) -> Path:
        rel = self.get(f"paths.{name}", name)
        p = ROOT / rel
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def root(self) -> Path:
        return ROOT


def load_config() -> Config:
    return Config.load()
