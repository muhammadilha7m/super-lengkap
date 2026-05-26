"""Tests for AppConfig persistence."""

from __future__ import annotations

import json
from pathlib import Path

from image_upscaler import config as config_mod
from image_upscaler.config import AppConfig


def test_app_data_dir_per_platform(monkeypatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "/tmp/appdata")
    assert config_mod.app_data_dir() == Path("/tmp/appdata/ImageUpscalerPro")

    monkeypatch.setattr(config_mod.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    assert config_mod.app_data_dir() == Path("/tmp/xdg/ImageUpscalerPro")


def test_load_returns_defaults_when_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_mod, "app_data_dir", lambda: tmp_path / "cfg")
    cfg = AppConfig.load()
    assert cfg.scale > 0
    assert cfg.output_format


def test_save_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_mod, "app_data_dir", lambda: tmp_path / "cfg")
    cfg = AppConfig()
    cfg.scale = 3
    cfg.output_format = "JPEG"
    cfg.accent_color = "purple"
    cfg.save()

    raw = json.loads((tmp_path / "cfg" / "config.json").read_text())
    assert raw["scale"] == 3
    assert raw["output_format"] == "JPEG"

    loaded = AppConfig.load()
    assert loaded.scale == 3
    assert loaded.output_format == "JPEG"
    assert loaded.accent_color == "purple"


def test_load_ignores_unknown_keys(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_mod, "app_data_dir", lambda: tmp_path / "cfg")
    target = tmp_path / "cfg" / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"scale": 2, "completely_unknown": "value"}))
    loaded = AppConfig.load()
    assert loaded.scale == 2


def test_remember_input_dir_dedupes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_mod, "app_data_dir", lambda: tmp_path / "cfg")
    cfg = AppConfig()
    cfg.remember_input_dir("/a")
    cfg.remember_input_dir("/b")
    cfg.remember_input_dir("/a")
    assert cfg.recent_input_dirs[:2] == ["/a", "/b"]


def test_load_recovers_from_corrupt_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config_mod, "app_data_dir", lambda: tmp_path / "cfg")
    target = tmp_path / "cfg" / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not json")
    cfg = AppConfig.load()
    assert cfg.scale > 0
