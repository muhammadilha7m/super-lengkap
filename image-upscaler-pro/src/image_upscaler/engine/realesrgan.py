"""Real-ESRGAN engine — wraps the ``realesrgan-ncnn-vulkan`` standalone binary.

The binary is provided by the upstream project at
https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases. It works on any
GPU that supports Vulkan (NVIDIA, AMD, Intel) and falls back to CPU.

We do NOT bundle the binary here. The user can either:
1. Drop ``realesrgan-ncnn-vulkan(.exe)`` plus the ``models`` folder into a
   ``bin/`` directory next to the app, or
2. Set an absolute path via the in-app settings (``config.realesrgan_binary``).

When the binary is missing the engine reports itself unavailable; the app
will then offer to fall back to Lanczos.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageOps

from ..constants import ENGINE_REALESRGAN, REALESRGAN_MODEL_SCALES, SCALE_PRESETS
from ..utils.image import save_image
from .base import EngineError, UpscaleEngine, UpscaleOptions

log = logging.getLogger(__name__)


def _candidate_binary_names() -> list[str]:
    if sys.platform.startswith("win"):
        return ["realesrgan-ncnn-vulkan.exe"]
    return ["realesrgan-ncnn-vulkan"]


def _search_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent.parent.parent.parent
    return [
        here / "bin",
        here,
        Path.cwd() / "bin",
        Path.cwd(),
    ]


def find_realesrgan_binary(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p
    for name in _candidate_binary_names():
        on_path = shutil.which(name)
        if on_path:
            return Path(on_path)
        for d in _search_dirs():
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


class RealEsrganEngine(UpscaleEngine):
    name = "realesrgan"
    display_name = ENGINE_REALESRGAN

    def __init__(self, binary_override: str = "") -> None:
        self.binary_override = binary_override
        self._binary = find_realesrgan_binary(binary_override)

    def available(self) -> tuple[bool, str]:
        if self._binary is None:
            return (
                False,
                "Binary 'realesrgan-ncnn-vulkan' tidak ditemukan. "
                "Letakkan di folder 'bin/' atau atur path di Settings.",
            )
        return True, ""

    def upscale(
        self,
        input_path: Path,
        output_path: Path,
        options: UpscaleOptions,
        cancel_event: threading.Event,
    ) -> None:
        if self._binary is None:
            raise EngineError(
                "Real-ESRGAN belum di-setup. Pakai engine Lanczos atau install binary-nya."
            )
        if options.scale not in SCALE_PRESETS:
            raise EngineError(
                f"Real-ESRGAN ncnn-vulkan hanya mendukung scale {SCALE_PRESETS}, "
                f"diminta x{options.scale}. Gunakan Lanczos untuk skala bebas."
            )
        if options.model:
            allowed = REALESRGAN_MODEL_SCALES.get(options.model)
            if allowed is not None and options.scale not in allowed:
                allowed_str = "/".join(f"{s}x" for s in allowed)
                raise EngineError(
                    f"Model '{options.model}' hanya mendukung {allowed_str}. "
                    f"Pilih skala yang sesuai, atau ganti model ke 'realesr-animevideov3' "
                    f"yang mendukung 2x/3x/4x."
                )

        with tempfile.TemporaryDirectory(prefix="iup_") as tmp_dir:
            tmp_in = Path(tmp_dir) / "in.png"
            tmp_out = Path(tmp_dir) / "out.png"
            self._stage_input(input_path, tmp_in, options)

            cmd = [
                str(self._binary),
                "-i",
                str(tmp_in),
                "-o",
                str(tmp_out),
                "-s",
                str(options.scale),
            ]
            if options.model:
                cmd += ["-n", options.model]

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self._binary.parent,
                    text=True,
                )
            except (OSError, FileNotFoundError) as exc:
                raise EngineError(f"Gagal menjalankan Real-ESRGAN: {exc}") from exc

            # Drain stdout/stderr in background threads. ncnn-vulkan streams
            # progress lines ("0.00%\n1.00%\n...") which would otherwise fill
            # the OS pipe buffer (~64 KB) and block the subprocess forever.
            stdout_buf: list[str] = []
            stderr_buf: list[str] = []
            t_out = self._spawn_reader(proc.stdout, stdout_buf)
            t_err = self._spawn_reader(proc.stderr, stderr_buf)

            try:
                while proc.poll() is None:
                    if cancel_event.wait(0.2):
                        self._terminate(proc)
                        raise EngineError("cancelled")
            finally:
                # Ensure pipes are fully drained even on early exit.
                if t_out is not None:
                    t_out.join(timeout=2)
                if t_err is not None:
                    t_err.join(timeout=2)

            stderr = "".join(stderr_buf).strip()
            stdout = "".join(stdout_buf).strip()
            if proc.returncode != 0:
                detail = stderr or stdout or "(no output)"
                raise EngineError(
                    f"Real-ESRGAN exit code {proc.returncode}: {detail}"
                )
            if not tmp_out.exists():
                detail = stderr or stdout or "(no output)"
                raise EngineError(
                    f"Real-ESRGAN selesai tapi output tidak terbuat. {detail}"
                )

            with Image.open(tmp_out) as result:
                result.load()
                with Image.open(input_path) as src:
                    exif_bytes = src.info.get("exif") if options.preserve_exif else None
                save_image(result, output_path, options, exif_bytes=exif_bytes)

    @staticmethod
    def _stage_input(src: Path, dst: Path, options: UpscaleOptions) -> None:
        """Copy/convert source into a PNG temp file Real-ESRGAN can read."""
        try:
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")
                img.save(dst, format="PNG", optimize=False)
        except (OSError, ValueError) as exc:
            raise EngineError(f"Tidak bisa membaca '{src.name}': {exc}") from exc
        if options is None:  # pragma: no cover - defensive
            return

    @staticmethod
    def _terminate(proc: subprocess.Popen[str]) -> None:
        try:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.kill()
        except OSError:
            pass

    @staticmethod
    def _spawn_reader(stream, sink: list[str]) -> threading.Thread | None:
        """Drain a Popen text stream into ``sink`` from a daemon thread."""
        if stream is None:
            return None

        def _pump() -> None:
            try:
                for chunk in iter(stream.readline, ""):
                    if not chunk:
                        break
                    sink.append(chunk)
            except (OSError, ValueError):
                pass
            finally:
                with contextlib.suppress(OSError):
                    stream.close()

        t = threading.Thread(target=_pump, name="iup-pipe-pump", daemon=True)
        t.start()
        return t
