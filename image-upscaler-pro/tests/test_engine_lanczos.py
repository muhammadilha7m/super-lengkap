"""Tests for the Lanczos engine."""

from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image

from image_upscaler.engine.base import UpscaleOptions
from image_upscaler.engine.lanczos import LanczosEngine


def _make_image(path: Path, size: tuple[int, int] = (32, 24), color=(255, 0, 0)) -> None:
    img = Image.new("RGB", size, color=color)
    img.save(path)


def test_lanczos_doubles_size(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    dst = tmp_path / "out.png"
    _make_image(src, (10, 5))
    LanczosEngine().upscale(
        src,
        dst,
        UpscaleOptions(scale=2, output_format="PNG"),
        threading.Event(),
    )
    assert dst.exists()
    with Image.open(dst) as out:
        assert out.size == (20, 10)


def test_lanczos_jpeg_quality_writes_jpeg(tmp_path: Path) -> None:
    src = tmp_path / "in.jpg"
    dst = tmp_path / "out.jpg"
    _make_image(src, (40, 30))
    LanczosEngine().upscale(
        src,
        dst,
        UpscaleOptions(scale=3, output_format="JPEG", jpeg_quality=90),
        threading.Event(),
    )
    with Image.open(dst) as out:
        assert out.format == "JPEG"
        assert out.size == (120, 90)


def test_lanczos_cancelled_raises(tmp_path: Path) -> None:
    src = tmp_path / "in.png"
    _make_image(src, (8, 8))
    event = threading.Event()
    event.set()
    import pytest

    from image_upscaler.engine.base import EngineError

    with pytest.raises(EngineError):
        LanczosEngine().upscale(
            src,
            tmp_path / "out.png",
            UpscaleOptions(scale=2, output_format="PNG"),
            event,
        )
