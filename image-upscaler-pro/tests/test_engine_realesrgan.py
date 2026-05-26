"""Tests for the Real-ESRGAN engine validation + subprocess plumbing.

We don't invoke the real ``realesrgan-ncnn-vulkan`` binary here (it requires
Vulkan / a GPU); instead we monkeypatch the binary lookup and the subprocess
call to exercise the engine's branching logic deterministically.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PIL import Image

from image_upscaler.engine.base import EngineError, UpscaleOptions
from image_upscaler.engine.realesrgan import RealEsrganEngine, _popen_silent_kwargs


def _make_image(path: Path, size: tuple[int, int] = (16, 16)) -> None:
    Image.new("RGB", size, color=(123, 222, 99)).save(path)


def test_unavailable_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "image_upscaler.engine.realesrgan.find_realesrgan_binary", lambda _override="": None
    )
    eng = RealEsrganEngine()
    ok, msg = eng.available()
    assert ok is False
    assert "tidak ditemukan" in msg


@pytest.mark.parametrize(
    ("model", "scale"),
    [
        ("realesrgan-x4plus", 2),
        ("realesrgan-x4plus", 3),
        ("realesrgan-x4plus-anime", 2),
        ("realesrgan-x4plus-anime", 3),
    ],
)
def test_incompatible_model_scale_rejected_upfront(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model: str, scale: int
) -> None:
    """User-reported regression: model+scale mismatch must fail fast.

    Picking realesrgan-x4plus at 3x previously hung because the binary couldn't
    find weights named ``realesrgan-x4plus-x3.param``. The engine now validates
    the combo before spawning anything.
    """
    fake_binary = tmp_path / "realesrgan-ncnn-vulkan"
    fake_binary.write_text("not actually executable")
    monkeypatch.setattr(
        "image_upscaler.engine.realesrgan.find_realesrgan_binary",
        lambda _override="": fake_binary,
    )

    src = tmp_path / "in.png"
    _make_image(src)

    eng = RealEsrganEngine()
    with pytest.raises(EngineError, match="hanya mendukung"):
        eng.upscale(
            src,
            tmp_path / "out.png",
            UpscaleOptions(scale=scale, output_format="PNG", model=model),
            threading.Event(),
        )


def test_pipe_draining_does_not_hang(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a binary spamming progress lines used to fill the OS pipe
    buffer (~64 KB) and block the subprocess. With background pipe pumps it
    must complete quickly even with megabytes of output.
    """
    fake_binary = tmp_path / "fake-realesrgan"
    # A tiny Python script that prints 200 KB to stderr (mimicking ncnn
    # progress spam), then writes a tiny PNG to its output path, then exits.
    fake_binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from PIL import Image\n"
        "argv = sys.argv\n"
        "out_path = argv[argv.index('-o') + 1]\n"
        "for _ in range(20000):\n"
        "    sys.stderr.write('0.00%\\n')\n"
        "sys.stderr.flush()\n"
        "Image.new('RGB', (4, 4), 'red').save(out_path)\n"
    )
    fake_binary.chmod(0o755)

    monkeypatch.setattr(
        "image_upscaler.engine.realesrgan.find_realesrgan_binary",
        lambda _override="": fake_binary,
    )
    # Use scale 4 (compatible with x4plus) so validation passes.
    src = tmp_path / "in.png"
    _make_image(src)
    eng = RealEsrganEngine()
    eng.upscale(
        src,
        tmp_path / "out.png",
        UpscaleOptions(scale=4, output_format="PNG", model="realesrgan-x4plus"),
        threading.Event(),
    )
    assert (tmp_path / "out.png").exists()


def test_popen_silent_kwargs_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows, Popen must receive CREATE_NO_WINDOW + hidden STARTUPINFO so
    no CMD console flashes when each job spawns the binary."""
    import subprocess as sp

    monkeypatch.setattr("sys.platform", "win32")
    # subprocess.STARTUPINFO only exists on Windows; stub it for the test.
    monkeypatch.setattr(
        sp,
        "STARTUPINFO",
        getattr(sp, "STARTUPINFO", lambda: type("SU", (), {"dwFlags": 0, "wShowWindow": 0})()),
        raising=False,
    )
    monkeypatch.setattr(sp, "STARTF_USESHOWWINDOW", 0x00000001, raising=False)
    kwargs = _popen_silent_kwargs()
    assert kwargs["creationflags"] == 0x08000000  # CREATE_NO_WINDOW
    assert "startupinfo" in kwargs


def test_popen_silent_kwargs_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    assert _popen_silent_kwargs() == {}


def test_nonzero_exit_surfaces_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_binary = tmp_path / "fake-realesrgan-fail"
    fake_binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stderr.write('vkCreateInstance failed -9\\n')\n"
        "sys.exit(99)\n"
    )
    fake_binary.chmod(0o755)
    monkeypatch.setattr(
        "image_upscaler.engine.realesrgan.find_realesrgan_binary",
        lambda _override="": fake_binary,
    )

    src = tmp_path / "in.png"
    _make_image(src)
    eng = RealEsrganEngine()
    with pytest.raises(EngineError, match="exit code 99"):
        eng.upscale(
            src,
            tmp_path / "out.png",
            UpscaleOptions(scale=4, output_format="PNG", model="realesrgan-x4plus"),
            threading.Event(),
        )
